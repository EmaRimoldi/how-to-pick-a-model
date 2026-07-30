#!/usr/bin/env python3
"""Power analysis conditioned on nonconfirmatory BF16 Stage 0 hazards."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


PRIOR = np.full(3, 1.0 / 3.0)
ALPHAS = (0.60, 0.80)
ALLOCATIONS = ("matched", "prior", "half_anti")
BASELINE = "Qwen/Qwen2.5-Coder-14B-Instruct"
DEPLOYED = "Qwen/Qwen2.5-Coder-7B-Instruct"


def percentile(values: list[float], probability: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def posterior(alpha: float, z: int) -> np.ndarray:
    result = np.full(3, (1.0 - alpha) / 2.0)
    result[z] = alpha
    return result


def allocation(alpha: float, z: int, name: str) -> np.ndarray:
    post = posterior(alpha, z)
    if name == "matched":
        return post
    if name == "prior":
        return PRIOR.copy()
    if name == "half_anti":
        return 0.5 * np.asarray((post[2], post[0], post[1])) + 0.5 * PRIOR
    raise ValueError(name)


def information(alpha: float) -> float:
    return float(
        sum(
            PRIOR[mode]
            * (alpha if mode == z else (1.0 - alpha) / 2.0)
            * math.log((alpha if mode == z else (1.0 - alpha) / 2.0) / PRIOR[z])
            for mode in range(3)
            for z in range(3)
        )
    )


def mismatch(alpha: float, name: str) -> float:
    return float(
        sum(
            PRIOR[z]
            * sum(
                value * math.log(value / share)
                for value, share in zip(posterior(alpha, z), allocation(alpha, z, name))
            )
            for z in range(3)
        )
    )


def heterogeneous_probabilities(
    rng: np.random.Generator, cell_mean: float, size: int, logit_sd: float
) -> np.ndarray:
    logit = math.log(cell_mean / (1.0 - cell_mean))
    probabilities = 1.0 / (1.0 + np.exp(-(logit + rng.normal(0.0, logit_sd, size))))
    return np.clip(probabilities, 0.01, 0.995)


def stratified_prototype_probabilities(
    rng: np.random.Generator,
    strata: list[dict[str, object]],
    tasks_per_mode: int,
) -> np.ndarray:
    if tasks_per_mode % len(strata) != 0:
        raise ValueError("tasks per mode must be divisible by the number of strata")
    per_stratum = tasks_per_mode // len(strata)
    probabilities = []
    for stratum in sorted(strata, key=lambda item: str(item["stratum"])):
        counts = np.asarray(stratum["success_counts"], dtype=int)
        attempts = int(stratum["attempts_per_task"])
        selected = rng.choice(counts, size=per_stratum, replace=True)
        probabilities.append(rng.beta(selected + 0.5, attempts - selected + 0.5))
    return np.concatenate(probabilities)


def calibrate_t0(
    rng: np.random.Generator, probabilities: np.ndarray, initial_attempts: int, max_attempts: int
) -> tuple[float, bool]:
    successes = rng.binomial(initial_attempts, probabilities)
    attempts = np.full(len(probabilities), initial_attempts)
    needs_extension = successes == 0
    if np.any(needs_extension):
        extension = max_attempts - initial_attempts
        successes[needs_extension] += rng.binomial(extension, probabilities[needs_extension])
        attempts[needs_extension] += extension
    if np.any(successes == 0):
        return math.inf, False
    task_means = attempts / successes
    return float(np.exp(np.mean(np.log(task_means)))), True


def physical_cell_mean(
    rng: np.random.Generator,
    probabilities: np.ndarray,
    q_true: float,
    repetitions: int,
    max_slots: int,
) -> tuple[float, float, bool]:
    draws = rng.geometric(q_true * probabilities, size=(repetitions, len(probabilities)))
    censored = draws > max_slots
    exposure = np.minimum(draws, max_slots)
    successes = np.sum(~censored, axis=0)
    if np.any(successes == 0):
        return math.inf, float(np.mean(censored)), False
    task_means = np.sum(exposure, axis=0) / successes
    return float(np.exp(np.mean(np.log(task_means)))), float(np.mean(censored)), True


def simulate_once(
    rng: np.random.Generator,
    hazards: dict[str, list[float]],
    prototypes: dict[tuple[str, int], list[dict[str, object]]],
    costs: dict[str, float],
    tasks_per_mode: int,
    calibration_attempts: int,
    calibration_max_attempts: int,
    confirmation_repetitions: int,
    max_slots: int,
    logit_sd: float,
    max_absolute_mean_residual: float,
    max_residual_rms: float,
    max_censoring: float,
) -> dict[str, float | bool]:
    if prototypes:
        calibration_probabilities = {
            (model, mode): stratified_prototype_probabilities(
                rng, prototypes[(model, mode)], tasks_per_mode
            )
            for model in hazards
            for mode in range(3)
        }
        confirmation_probabilities = {
            (model, mode): stratified_prototype_probabilities(
                rng, prototypes[(model, mode)], tasks_per_mode
            )
            for model in hazards
            for mode in range(3)
        }
    else:
        calibration_probabilities = {
            (model, mode): heterogeneous_probabilities(rng, hazards[model][mode], tasks_per_mode, logit_sd)
            for model in hazards
            for mode in range(3)
        }
        confirmation_probabilities = {
            (model, mode): heterogeneous_probabilities(rng, hazards[model][mode], tasks_per_mode, logit_sd)
            for model in hazards
            for mode in range(3)
        }
    t0 = {}
    identified = True
    for key, probabilities in calibration_probabilities.items():
        t0[key], cell_identified = calibrate_t0(
            rng, probabilities, calibration_attempts, calibration_max_attempts
        )
        identified &= cell_identified
    if not identified:
        return {"identified": False, "closure_pass": False, "censoring": 1.0, "mean_residual": math.inf, "rms": math.inf}

    baseline_log = 0.0
    censoring_rates = []
    for mode in range(3):
        cell_mean, censoring, cell_identified = physical_cell_mean(
            rng,
            confirmation_probabilities[(BASELINE, mode)],
            1.0 / 3.0,
            confirmation_repetitions,
            max_slots,
        )
        if not cell_identified:
            return {"identified": False, "closure_pass": False, "censoring": censoring, "mean_residual": math.inf, "rms": math.inf}
        baseline_log += PRIOR[mode] * math.log(costs[BASELINE] * cell_mean)
        censoring_rates.append(censoring)

    residuals = []
    for alpha in ALPHAS:
        for name in ALLOCATIONS:
            deployed_log = 0.0
            for mode in range(3):
                for z in range(3):
                    channel = alpha if mode == z else (1.0 - alpha) / 2.0
                    q_true = float(allocation(alpha, z, name)[mode])
                    cell_mean, censoring, cell_identified = physical_cell_mean(
                        rng,
                        confirmation_probabilities[(DEPLOYED, mode)],
                        q_true,
                        confirmation_repetitions,
                        max_slots,
                    )
                    if not cell_identified:
                        return {"identified": False, "closure_pass": False, "censoring": censoring, "mean_residual": math.inf, "rms": math.inf}
                    deployed_log += PRIOR[mode] * channel * math.log(costs[DEPLOYED] * cell_mean)
                    censoring_rates.append(censoring)
            observed = baseline_log - deployed_log
            unit_cost = math.log(costs[BASELINE] / costs[DEPLOYED])
            competence = float(
                np.mean([math.log(t0[(BASELINE, mode)] / t0[(DEPLOYED, mode)]) for mode in range(3)])
            )
            predicted = unit_cost + competence + information(alpha) - mismatch(alpha, name)
            residuals.append(observed - predicted)

    mean_residual = float(np.mean(residuals))
    rms = float(np.sqrt(np.mean(np.square(residuals))))
    observed_max_censoring = max(censoring_rates)
    return {
        "identified": True,
        "mean_residual": mean_residual,
        "rms": rms,
        "censoring": observed_max_censoring,
        "closure_pass": (
            abs(mean_residual) <= max_absolute_mean_residual
            and rms <= max_residual_rms
            and observed_max_censoring <= max_censoring
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage0", type=Path, required=True)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument("--tasks-per-mode", type=int, nargs="+", default=(128, 192, 256))
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--calibration-attempts", type=int, default=64)
    parser.add_argument("--calibration-max-attempts", type=int, default=128)
    parser.add_argument("--confirmation-repetitions", type=int, default=6)
    parser.add_argument("--max-slots", type=int, default=256)
    parser.add_argument("--task-logit-sd", type=float, default=0.25)
    parser.add_argument("--max-absolute-mean-residual", type=float, default=0.10)
    parser.add_argument("--max-residual-rms", type=float, default=0.15)
    parser.add_argument("--max-censoring", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stage0 = json.loads(args.stage0.read_text(encoding="utf-8"))
    hazards = {
        model: [float(cell["rate"]) for cell in sorted(spec["matched_by_mode"], key=lambda item: item["mode"])]
        for model, spec in stage0["models"].items()
    }
    prototypes = {
        (model, mode): [
            item
            for item in spec.get("task_success_counts_by_mode_and_stratum", [])
            if int(item["mode"]) == mode
        ]
        for model, spec in stage0["models"].items()
        for mode in range(3)
    }
    if not all(prototypes.values()):
        prototypes = {}
    cost_document = json.loads(args.costs.read_text(encoding="utf-8"))
    costs = {model: float(spec["kappa"]) for model, spec in cost_document["models"].items()}
    rng = np.random.default_rng(args.seed)
    summaries = {}
    for tasks_per_mode in args.tasks_per_mode:
        records = [
            simulate_once(
                rng,
                hazards,
                prototypes,
                costs,
                tasks_per_mode,
                args.calibration_attempts,
                args.calibration_max_attempts,
                args.confirmation_repetitions,
                args.max_slots,
                args.task_logit_sd,
                args.max_absolute_mean_residual,
                args.max_residual_rms,
                args.max_censoring,
            )
            for _ in range(args.replicates)
        ]
        finite = [record for record in records if bool(record["identified"])]
        summaries[str(tasks_per_mode)] = {
            "identification_probability": len(finite) / len(records),
            "closure_gate_probability": sum(bool(record["closure_pass"]) for record in records) / len(records),
            "absolute_mean_residual_p95_nats": percentile([abs(float(record["mean_residual"])) for record in finite], 0.95),
            "residual_rms_p95_nats": percentile([float(record["rms"]) for record in finite], 0.95),
            "max_cell_censoring_p95": percentile([float(record["censoring"]) for record in finite], 0.95),
        }
    result = {
        "schema_version": 1,
        "analysis": "stage0_conditioned_packed_null_power",
        "evidence_status": "design_only_not_theorem_evidence",
        "stage0": str(args.stage0),
        "hazards": hazards,
        "task_probability_model": (
            "stratified_beta_posterior_resampling_of_stage0_task_counts"
            if prototypes
            else "logistic_normal_sensitivity"
        ),
        "costs": costs,
        "replicates": args.replicates,
        "calibration_attempts": args.calibration_attempts,
        "calibration_max_attempts": args.calibration_max_attempts,
        "confirmation_repetitions": args.confirmation_repetitions,
        "max_slots": args.max_slots,
        "task_logit_sd": args.task_logit_sd,
        "gates": {
            "max_absolute_mean_residual_nats": args.max_absolute_mean_residual,
            "max_residual_rms_nats": args.max_residual_rms,
            "max_censoring": args.max_censoring,
        },
        "sample_sizes": summaries,
        "seed": args.seed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
