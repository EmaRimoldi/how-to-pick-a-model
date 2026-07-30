#!/usr/bin/env python3
"""Synthetic design sensitivity analysis for the four-term protocol.

This script intentionally reads no empirical result. It evaluates whether the
planned split sizes can recover packedness, held-out closure, and model choice
over a broad, preregistered focused-success regime.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


K = 3
ALPHAS = (1.0 / 3.0, 0.60, 0.80)
MODEL_NAMES = ("3B", "7B", "14B")
KAPPAS = np.asarray((1.0, 2.0, 4.0), dtype=float)
# Hypothetical values spanning the protocol's admissible regime. They are not
# estimates from this repository or claims about the named checkpoints.
PASS_MEANS = np.asarray(
    (
        (0.15, 0.18, 0.23),
        (0.27, 0.32, 0.38),
        (0.43, 0.50, 0.58),
    ),
    dtype=float,
)
Q_LEVELS = np.asarray((0.125, 0.20, 1.0 / 3.0, 0.50, 0.80))


def posterior(alpha: float) -> np.ndarray:
    result = np.full((K, K), (1.0 - alpha) / (K - 1), dtype=float)
    np.fill_diagonal(result, alpha)
    return result


def allocations(alpha: float) -> dict[str, np.ndarray]:
    post = posterior(alpha)
    prior = np.full((K, K), 1.0 / K)
    anti = np.vstack([np.roll(post[z], 1) for z in range(K)])
    return {
        "matched": post,
        "half_prior": 0.5 * post + 0.5 * prior,
        "prior": prior,
        "half_anti": 0.5 * anti + 0.5 * prior,
    }


def information_and_mismatch(alpha: float, q: np.ndarray) -> tuple[float, float]:
    post = posterior(alpha)
    conditional_entropy = -np.mean(np.sum(post * np.log(post), axis=1))
    information = math.log(K) - conditional_entropy
    mismatch = np.mean(np.sum(post * np.log(post / q), axis=1))
    return float(information), float(mismatch)


def draw_task_probabilities(
    rng: np.random.Generator, mean: float, size: int
) -> np.ndarray:
    logit_mean = math.log(mean / (1.0 - mean))
    values = 1.0 / (1.0 + np.exp(-(logit_mean + rng.normal(0.0, 0.25, size))))
    return np.clip(values, 0.08, 0.75)


def estimate_t0(
    rng: np.random.Generator, model: int, mode: int, sample_size: int
) -> float:
    probabilities = draw_task_probabilities(
        rng, PASS_MEANS[model, mode], sample_size
    )
    return float(np.mean(rng.geometric(probabilities)))


def estimate_kappa(rng: np.random.Generator, model: int) -> float:
    # Four hundred isolated fixed-slot profiler measurements with 5% CV.
    samples = KAPPAS[model] * np.exp(rng.normal(-0.5 * 0.05**2, 0.05, 400))
    return float(np.mean(samples))


def observed_log_resource(
    rng: np.random.Generator,
    model: int,
    alpha: float,
    q: np.ndarray,
    sample_size: int,
) -> float:
    post = posterior(alpha)
    value = 0.0
    for mode in range(K):
        for signal in range(K):
            probabilities = draw_task_probabilities(
                rng, PASS_MEANS[model, mode], sample_size
            )
            useful_slots = rng.geometric(probabilities)
            total_resource = KAPPAS[model] * useful_slots / q[signal, mode]
            cell_mean = float(np.mean(total_resource))
            value += post[signal, mode] * math.log(cell_mean) / K
    return value


def observed_baseline_log_resource(
    rng: np.random.Generator, sample_size: int
) -> float:
    cells = []
    baseline = len(MODEL_NAMES) - 1
    for mode in range(K):
        probabilities = draw_task_probabilities(
            rng, PASS_MEANS[baseline, mode], sample_size
        )
        useful_slots = rng.geometric(probabilities)
        cells.append(float(np.mean(KAPPAS[baseline] * useful_slots * K)))
    return float(np.mean(np.log(cells)))


def packedness_slope(rng: np.random.Generator, sample_size: int) -> float:
    x_values: list[float] = []
    y_values: list[float] = []
    cell_values: list[int] = []
    for model in range(len(MODEL_NAMES)):
        for mode in range(K):
            for share in Q_LEVELS:
                probabilities = draw_task_probabilities(
                    rng, PASS_MEANS[model, mode], sample_size
                )
                useful_slots = rng.geometric(probabilities)
                resource = KAPPAS[model] * useful_slots / share
                x_values.append(-math.log(share))
                y_values.append(math.log(float(np.mean(resource))))
                cell_values.append(model * K + mode)

    x = np.asarray(x_values)
    y = np.asarray(y_values)
    cells = np.asarray(cell_values)
    x_demeaned = np.empty_like(x)
    y_demeaned = np.empty_like(y)
    for cell in np.unique(cells):
        selected = cells == cell
        x_demeaned[selected] = x[selected] - np.mean(x[selected])
        y_demeaned[selected] = y[selected] - np.mean(y[selected])
    return float(np.dot(x_demeaned, y_demeaned) / np.dot(x_demeaned, x_demeaned))


def concordance(predicted: np.ndarray, observed: np.ndarray) -> float:
    concordant = 0
    total = 0
    for left in range(len(predicted)):
        for right in range(left + 1, len(predicted)):
            pred_delta = predicted[left] - predicted[right]
            obs_delta = observed[left] - observed[right]
            if pred_delta == 0.0 or obs_delta == 0.0:
                continue
            concordant += int(np.sign(pred_delta) == np.sign(obs_delta))
            total += 1
    return (2.0 * concordant / total - 1.0) if total else 0.0


def simulate_once(
    rng: np.random.Generator, sample_size: int, closure_tolerance: float
) -> dict[str, float | bool]:
    t0 = np.empty_like(PASS_MEANS)
    kappa = np.empty(len(MODEL_NAMES))
    for model in range(len(MODEL_NAMES)):
        kappa[model] = estimate_kappa(rng, model)
        for mode in range(K):
            t0[model, mode] = estimate_t0(rng, model, mode, sample_size)

    baseline = len(MODEL_NAMES) - 1
    observed_baseline = observed_baseline_log_resource(rng, sample_size)
    residuals: list[float] = []
    predicted_scores: list[float] = []
    observed_scores: list[float] = []
    design_keys: list[tuple[int, float, str]] = []

    for model in range(len(MODEL_NAMES)):
        for alpha in ALPHAS:
            for policy_name, q in allocations(alpha).items():
                information, mismatch = information_and_mismatch(alpha, q)
                observed = observed_log_resource(
                    rng, model, alpha, q, sample_size
                )
                cost = math.log(kappa[baseline] / kappa[model])
                competence = float(np.mean(np.log(t0[baseline] / t0[model])))
                predicted_gain = cost + competence + information - mismatch
                observed_gain = observed_baseline - observed
                residuals.append(observed_gain - predicted_gain)

                score = (
                    math.log(kappa[model])
                    + float(np.mean(np.log(t0[model])))
                    + math.log(K)
                    - information
                    + mismatch
                )
                predicted_scores.append(score)
                observed_scores.append(observed)
                design_keys.append((model, alpha, policy_name))

    residual_array = np.asarray(residuals)
    predicted_array = np.asarray(predicted_scores)
    observed_array = np.asarray(observed_scores)

    fixed_indices = [
        index
        for index, (_, alpha, policy) in enumerate(design_keys)
        if alpha == 0.80 and policy == "matched"
    ]
    predicted_fixed = fixed_indices[int(np.argmin(predicted_array[fixed_indices]))]
    observed_fixed = fixed_indices[int(np.argmin(observed_array[fixed_indices]))]
    predicted_system = int(np.argmin(predicted_array))
    observed_system = int(np.argmin(observed_array))
    system_regret = (
        math.exp(observed_array[predicted_system] - observed_array[observed_system]) - 1.0
    )

    slope = packedness_slope(rng, sample_size)
    return {
        "max_abs_residual": float(np.max(np.abs(residual_array))),
        "residual_rms": float(np.sqrt(np.mean(residual_array**2))),
        "closure_within_tolerance": bool(
            np.max(np.abs(residual_array)) <= closure_tolerance
        ),
        "packedness_slope": slope,
        "slope_within_equivalence": bool(0.90 <= slope <= 1.10),
        "fixed_signal_model_selected": predicted_fixed == observed_fixed,
        "full_system_selected": predicted_system == observed_system,
        "system_regret_fraction": float(system_regret),
        "rank_concordance": concordance(predicted_array, observed_array),
    }


def summarize(records: list[dict[str, float | bool]]) -> dict[str, float]:
    def values(key: str) -> np.ndarray:
        return np.asarray([record[key] for record in records], dtype=float)

    return {
        "simultaneous_closure_probability": float(
            np.mean(values("closure_within_tolerance"))
        ),
        "max_abs_residual_p95_nats": float(
            np.quantile(values("max_abs_residual"), 0.95)
        ),
        "residual_rms_p95_nats": float(
            np.quantile(values("residual_rms"), 0.95)
        ),
        "packedness_slope_mean": float(np.mean(values("packedness_slope"))),
        "packedness_slope_p025": float(
            np.quantile(values("packedness_slope"), 0.025)
        ),
        "packedness_slope_p975": float(
            np.quantile(values("packedness_slope"), 0.975)
        ),
        "packedness_equivalence_probability": float(
            np.mean(values("slope_within_equivalence"))
        ),
        "fixed_signal_model_selection_probability": float(
            np.mean(values("fixed_signal_model_selected"))
        ),
        "full_system_selection_probability": float(
            np.mean(values("full_system_selected"))
        ),
        "system_regret_p95_fraction": float(
            np.quantile(values("system_regret_fraction"), 0.95)
        ),
        "rank_concordance_mean": float(np.mean(values("rank_concordance"))),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=500)
    parser.add_argument(
        "--sample-sizes", type=int, nargs="+", default=(64, 128, 192, 256)
    )
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--closure-tolerance", type=float, default=0.15)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.replicates <= 0 or any(size <= 0 for size in args.sample_sizes):
        raise SystemExit("replicates and sample sizes must be positive")

    rng = np.random.default_rng(args.seed)
    result = {
        "design_only": True,
        "uses_repository_results": False,
        "seed": args.seed,
        "replicates": args.replicates,
        "closure_tolerance_nats": args.closure_tolerance,
        "assumptions": {
            "models": list(MODEL_NAMES),
            "normalized_kappas": KAPPAS.tolist(),
            "hypothetical_pass_means": PASS_MEANS.tolist(),
            "task_logit_sd": 0.25,
            "off_diagonal_hazard_ratio": 0.0,
        },
        "channel_terms": {
            str(alpha): {
                name: {
                    "information_nats": information_and_mismatch(alpha, q)[0],
                    "mismatch_nats": information_and_mismatch(alpha, q)[1],
                }
                for name, q in allocations(alpha).items()
            }
            for alpha in ALPHAS
        },
        "sample_sizes": {},
    }
    for sample_size in args.sample_sizes:
        records = [
            simulate_once(rng, sample_size, args.closure_tolerance)
            for _ in range(args.replicates)
        ]
        result["sample_sizes"][str(sample_size)] = summarize(records)

    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
