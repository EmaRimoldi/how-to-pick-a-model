#!/usr/bin/env python3
"""Estimate the four-term identity from disjoint SAI-3 splits."""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable


PRIOR = (1.0 / 3.0,) * 3


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def channel_probability(alpha: float, mode: int, z: int) -> float:
    return alpha if mode == z else (1.0 - alpha) / 2.0


def load_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def calibration_task_scales(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str], float]:
    counts: dict[tuple[str, int, str], list[int]] = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row["relation"] != "matched":
            continue
        key = (row["model"], int(row["mode"]), row["task_id"])
        counts[key][0] += bool(row["verification"]["passed"])
        counts[key][1] += 1
    zero_success = [key for key, (successes, _trials) in counts.items() if successes == 0]
    if zero_success:
        raise ValueError(f"focused calibration has zero-success task cells: {zero_success[:5]}")
    return {key: trials / successes for key, (successes, trials) in counts.items()}


def focused_scales(
    task_scales: dict[tuple[str, int, str], float],
    sampled_tasks: dict[int, list[str]] | None = None,
) -> dict[tuple[str, int], float]:
    values: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    if sampled_tasks is None:
        for (model, mode, _task), scale in task_scales.items():
            values[(model, mode)].append(scale)
    else:
        models = sorted({key[0] for key in task_scales})
        for model in models:
            for mode, task_ids in sampled_tasks.items():
                values[(model, mode)].extend(task_scales[(model, mode, task_id)] for task_id in task_ids)
    return {key: mean(cell_values) for key, cell_values in values.items()}


def trajectory_task_means(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str, int, int, str], float]:
    groups: dict[tuple[str, str, int, int, str], list[float]] = collections.defaultdict(list)
    for row in rows:
        if row.get("design") != "four_term":
            continue
        z = int(row["z"]) if "z" in row else -1
        value = float(row["total_slots"])
        if row.get("censored"):
            value += 1.0
        groups[(row["model"], row["condition"], int(row["mode"]), z, row["task_id"])].append(value)
    return {key: mean(values) for key, values in groups.items()}


def trajectory_cells(
    task_means: dict[tuple[str, str, int, int, str], float],
    sampled_tasks: dict[int, list[str]] | None = None,
) -> dict[tuple[str, str, int, int], float]:
    values: dict[tuple[str, str, int, int], list[float]] = collections.defaultdict(list)
    if sampled_tasks is None:
        for (model, condition, mode, z, _task), task_mean in task_means.items():
            values[(model, condition, mode, z)].append(task_mean)
    else:
        cell_keys = sorted({(model, condition, mode, z) for model, condition, mode, z, _task in task_means})
        for model, condition, mode, z in cell_keys:
            for task_id in sampled_tasks[mode]:
                values[(model, condition, mode, z)].append(
                    task_means[(model, condition, mode, z, task_id)]
                )
    return {key: mean(cell_values) for key, cell_values in values.items()}


def observed_delta(
    cells: dict[tuple[str, str, int, int], float],
    costs: dict[str, float],
    baseline_model: str,
    deployed_model: str,
    condition: str,
    alpha: float,
) -> float:
    baseline = sum(
        PRIOR[mode] * math.log(costs[baseline_model] * cells[(baseline_model, "baseline_prior", mode, -1)])
        for mode in range(3)
    )
    deployed = sum(
        PRIOR[mode]
        * channel_probability(alpha, mode, z)
        * math.log(costs[deployed_model] * cells[(deployed_model, condition, mode, z)])
        for mode in range(3)
        for z in range(3)
    )
    return baseline - deployed


def predicted_terms(
    scales: dict[tuple[str, int], float],
    costs: dict[str, float],
    baseline_model: str,
    deployed_model: str,
    information: float,
    mismatch: float,
) -> dict[str, float]:
    unit_cost = math.log(costs[baseline_model] / costs[deployed_model])
    competence = sum(
        PRIOR[mode] * math.log(scales[(baseline_model, mode)] / scales[(deployed_model, mode)])
        for mode in range(3)
    )
    return {
        "unit_cost_nats": unit_cost,
        "competence_nats": competence,
        "information_nats": information,
        "mismatch_nats": mismatch,
        "predicted_delta_nats": unit_cost + competence + information - mismatch,
    }


def shared_tasks(keys: Iterable[tuple[Any, ...]], task_index: int, mode_index: int) -> dict[int, list[str]]:
    by_mode: dict[int, set[str]] = collections.defaultdict(set)
    for key in keys:
        by_mode[int(key[mode_index])].add(str(key[task_index]))
    return {mode: sorted(task_ids) for mode, task_ids in by_mode.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, nargs="+", required=True)
    parser.add_argument("--confirmation", type=Path, nargs="+", required=True)
    parser.add_argument("--design-manifest", type=Path, required=True)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument("--baseline-model", required=True)
    parser.add_argument("--deployed-model", required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--max-absolute-mean-residual", type=float, default=0.10)
    parser.add_argument("--max-residual-rms", type=float, default=0.15)
    parser.add_argument("--max-rms-upper-95", type=float, default=0.20)
    parser.add_argument("--max-censoring", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    calibration_rows = load_jsonl(args.calibration)
    confirmation_rows = load_jsonl(args.confirmation)
    task_scales = calibration_task_scales(calibration_rows)
    scales = focused_scales(task_scales)
    task_means = trajectory_task_means(confirmation_rows)
    cells = trajectory_cells(task_means)
    manifest = json.loads(args.design_manifest.read_text(encoding="utf-8"))
    cost_document = json.loads(args.costs.read_text(encoding="utf-8"))
    costs = {model: float(spec["kappa"]) for model, spec in cost_document["models"].items()}
    for model in (args.baseline_model, args.deployed_model):
        if model not in costs:
            raise SystemExit(f"missing cost for {model}")

    term_specs = {
        (float(item["alpha"]), item["allocation"]): item
        for item in manifest["terms"]
    }
    comparisons = [
        (args.baseline_model, args.baseline_model, "self_baseline"),
        (args.deployed_model, args.deployed_model, "self_deployed"),
        (args.baseline_model, args.deployed_model, "cross_model_primary"),
    ]
    results = []
    for baseline_model, deployed_model, label in comparisons:
        for (alpha, allocation), term_spec in sorted(term_specs.items()):
            condition = f"alpha={alpha:.8f}|allocation={allocation}"
            observed = observed_delta(cells, costs, baseline_model, deployed_model, condition, alpha)
            terms = predicted_terms(
                scales,
                costs,
                baseline_model,
                deployed_model,
                float(term_spec["information_nats"]),
                float(term_spec["mismatch_nats"]),
            )
            results.append(
                {
                    "comparison": label,
                    "baseline_model": baseline_model,
                    "deployed_model": deployed_model,
                    "alpha": alpha,
                    "allocation": allocation,
                    "condition": condition,
                    "observed_delta_nats": observed,
                    **terms,
                    "residual_nats": observed - terms["predicted_delta_nats"],
                }
            )

    calibration_ids = shared_tasks(task_scales, task_index=2, mode_index=1)
    confirmation_ids = shared_tasks(task_means, task_index=4, mode_index=2)
    rng = random.Random(args.seed)
    bootstrap_residuals: dict[tuple[str, float, str], list[float]] = collections.defaultdict(list)
    bootstrap_primary_rms = []
    for _ in range(args.bootstrap_repetitions):
        sampled_calibration = {
            mode: [rng.choice(task_ids) for _ in task_ids]
            for mode, task_ids in calibration_ids.items()
        }
        sampled_confirmation = {
            mode: [rng.choice(task_ids) for _ in task_ids]
            for mode, task_ids in confirmation_ids.items()
        }
        sampled_scales = focused_scales(task_scales, sampled_calibration)
        sampled_cells = trajectory_cells(task_means, sampled_confirmation)
        primary_residuals = []
        for baseline_model, deployed_model, label in comparisons:
            for (alpha, allocation), term_spec in sorted(term_specs.items()):
                condition = f"alpha={alpha:.8f}|allocation={allocation}"
                observed = observed_delta(
                    sampled_cells, costs, baseline_model, deployed_model, condition, alpha
                )
                terms = predicted_terms(
                    sampled_scales,
                    costs,
                    baseline_model,
                    deployed_model,
                    float(term_spec["information_nats"]),
                    float(term_spec["mismatch_nats"]),
                )
                residual = observed - terms["predicted_delta_nats"]
                bootstrap_residuals[(label, alpha, allocation)].append(residual)
                if label == "cross_model_primary":
                    primary_residuals.append(residual)
        bootstrap_primary_rms.append(math.sqrt(mean(value * value for value in primary_residuals)))

    for result in results:
        samples = bootstrap_residuals[(result["comparison"], result["alpha"], result["allocation"])]
        result["residual_ci_95_nats"] = [percentile(samples, 0.025), percentile(samples, 0.975)]

    primary = [result for result in results if result["comparison"] == "cross_model_primary"]
    primary_residuals = [float(result["residual_nats"]) for result in primary]
    primary_mean = mean(primary_residuals)
    primary_rms = math.sqrt(mean(value * value for value in primary_residuals))
    censoring_rate = sum(bool(row.get("censored")) for row in confirmation_rows) / len(confirmation_rows)
    rms_upper = percentile(bootstrap_primary_rms, 0.95)
    gates = {
        "mean_residual_pass": abs(primary_mean) <= args.max_absolute_mean_residual,
        "residual_rms_pass": primary_rms <= args.max_residual_rms,
        "rms_upper_95_pass": rms_upper <= args.max_rms_upper_95,
        "censoring_pass": censoring_rate <= args.max_censoring,
    }
    summary = {
        "schema_version": 1,
        "analysis": "held_out_four_term_closure",
        "baseline_model": args.baseline_model,
        "deployed_model": args.deployed_model,
        "clock": cost_document["clock"],
        "costs": costs,
        "focused_scales": [
            {"model": model, "mode": mode, "t0_slots": value}
            for (model, mode), value in sorted(scales.items())
        ],
        "confirmation_trajectories": len(confirmation_rows),
        "censoring_rate": censoring_rate,
        "primary_weighted_mean_residual_nats": primary_mean,
        "primary_residual_rms_nats": primary_rms,
        "primary_residual_rms_upper_95_nats": rms_upper,
        "results": results,
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "INCONCLUSIVE_OR_FALSIFIED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
