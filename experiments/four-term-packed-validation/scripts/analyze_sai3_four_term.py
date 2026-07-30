#!/usr/bin/env python3
"""Estimate the four-term identity from disjoint SAI-3 splits."""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))

from runtime_provenance import sha256_path  # noqa: E402


PRIOR = (1.0 / 3.0,) * 3


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def geometric_mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return math.exp(mean(math.log(value) for value in materialized))


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def wilson_interval(
    successes: int, trials: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    if trials == 0:
        return math.nan, math.nan
    probability = successes / trials
    denominator = 1.0 + z * z / trials
    center = (probability + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(probability * (1.0 - probability) / trials + z * z / (4.0 * trials * trials))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def simple_slope(points: Iterable[tuple[float, float]]) -> float:
    materialized = list(points)
    x_mean = mean(x for x, _ in materialized)
    y_mean = mean(y for _, y in materialized)
    denominator = sum((x - x_mean) ** 2 for x, _ in materialized)
    if denominator <= 0.0:
        return math.nan
    return sum((x - x_mean) * (y - y_mean) for x, y in materialized) / denominator


def fixed_effect_slope(cells: Iterable[tuple[str, int, float, float]]) -> float:
    groups: dict[tuple[str, int], list[tuple[float, float]]] = collections.defaultdict(list)
    for model, mode, q_true, mean_slots in cells:
        groups[(model, mode)].append((-math.log(q_true), math.log(mean_slots)))
    numerator = 0.0
    denominator = 0.0
    for points in groups.values():
        x_mean = mean(x for x, _ in points)
        y_mean = mean(y for _, y in points)
        numerator += sum((x - x_mean) * (y - y_mean) for x, y in points)
        denominator += sum((x - x_mean) ** 2 for x, _ in points)
    return numerator / denominator


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=p_values.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, name in enumerate(ordered):
        running = max(running, (total - rank) * p_values[name])
        adjusted[name] = min(1.0, running)
    return adjusted


def channel_probability(alpha: float, mode: int, z: int) -> float:
    return alpha if mode == z else (1.0 - alpha) / 2.0


def load_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def calibration_task_scales(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str, str], float]:
    counts: dict[tuple[str, int, str, str], list[int]] = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row["relation"] != "matched":
            continue
        key = (row["model"], int(row["mode"]), row["task_stratum"], row["task_id"])
        counts[key][0] += bool(row["verification"]["passed"])
        counts[key][1] += 1
    zero_success = [key for key, (successes, _trials) in counts.items() if successes == 0]
    if zero_success:
        raise ValueError(f"focused calibration has zero-success task cells: {zero_success[:5]}")
    return {key: trials / successes for key, (successes, trials) in counts.items()}


def focused_scales(
    task_scales: dict[tuple[str, int, str, str], float],
    sampled_tasks: dict[tuple[int, str], list[str]] | None = None,
) -> dict[tuple[str, int], float]:
    values: dict[tuple[str, int], list[float]] = collections.defaultdict(list)
    if sampled_tasks is None:
        for (model, mode, _stratum, _task), scale in task_scales.items():
            values[(model, mode)].append(scale)
    else:
        models = sorted({key[0] for key in task_scales})
        for model in models:
            for (mode, stratum), task_ids in sampled_tasks.items():
                values[(model, mode)].extend(
                    task_scales[(model, mode, stratum, task_id)] for task_id in task_ids
                )
    # The theorem's estimand is E_s[log t0(M,s)], so each reported scale is
    # the geometric task mean whose logarithm equals that expected log-scale.
    return {key: geometric_mean(cell_values) for key, cell_values in values.items()}


def trajectory_task_means(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str, int, int, str, str], float]:
    groups: dict[tuple[str, str, int, int, str, str], list[int]] = collections.defaultdict(
        lambda: [0, 0]
    )
    for row in rows:
        if row.get("design") != "four_term":
            continue
        z = int(row["z"]) if "z" in row else -1
        key = (
            row["model"],
            row["condition"],
            int(row["mode"]),
            z,
            row["task_stratum"],
            row["task_id"],
        )
        groups[key][0] += int(row["total_slots"])
        groups[key][1] += bool(row.get("success"))
    unidentified = [key for key, (_exposure, successes) in groups.items() if successes == 0]
    if unidentified:
        raise ValueError(f"confirmation has all-censored task cells: {unidentified[:5]}")
    return {key: exposure / successes for key, (exposure, successes) in groups.items()}


def trajectory_cells(
    task_means: dict[tuple[str, str, int, int, str, str], float],
    sampled_tasks: dict[tuple[int, str], list[str]] | None = None,
) -> dict[tuple[str, str, int, int], float]:
    values: dict[tuple[str, str, int, int], list[float]] = collections.defaultdict(list)
    if sampled_tasks is None:
        for (model, condition, mode, z, _stratum, _task), task_mean in task_means.items():
            values[(model, condition, mode, z)].append(task_mean)
    else:
        cell_keys = sorted(
            {(model, condition, mode, z) for model, condition, mode, z, _stratum, _task in task_means}
        )
        for model, condition, mode, z in cell_keys:
            strata = sorted(stratum for candidate_mode, stratum in sampled_tasks if candidate_mode == mode)
            for stratum in strata:
                for task_id in sampled_tasks[(mode, stratum)]:
                    values[(model, condition, mode, z)].append(
                        task_means[(model, condition, mode, z, stratum, task_id)]
                    )
    # Aggregate task-specific first-passage means on the theorem's log scale.
    return {key: geometric_mean(cell_values) for key, cell_values in values.items()}


def calibration_diagnostics(
    rows: list[dict[str, Any]], initial_attempts: int, bootstrap_repetitions: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    models = sorted({str(row["model"]) for row in rows})
    hazard_rows = []
    trend_rows = []
    rng = random.Random(seed)
    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        matched = [row for row in model_rows if row["relation"] == "matched"]
        wrong = [row for row in model_rows if row["relation"] == "wrong"]
        matched_successes = sum(bool(row["verification"]["passed"]) for row in matched)
        wrong_successes = sum(bool(row["verification"]["passed"]) for row in wrong)
        matched_lower, matched_upper = wilson_interval(matched_successes, len(matched))
        wrong_lower, wrong_upper = wilson_interval(wrong_successes, len(wrong))
        hazard_rows.append(
            {
                "model": model,
                "matched_successes": matched_successes,
                "matched_trials": len(matched),
                "matched_hazard": matched_successes / len(matched),
                "matched_hazard_ci_95": [matched_lower, matched_upper],
                "off_diagonal_successes": wrong_successes,
                "off_diagonal_trials": len(wrong),
                "off_diagonal_hazard": wrong_successes / len(wrong),
                "off_diagonal_hazard_ci_95": [wrong_lower, wrong_upper],
                "off_diagonal_to_matched_upper_95": wrong_upper / matched_lower,
            }
        )

        by_task: dict[tuple[int, str, str], list[dict[str, Any]]] = collections.defaultdict(list)
        for row in matched:
            if int(row["attempt"]) < initial_attempts:
                by_task[(int(row["mode"]), row["task_stratum"], row["task_id"])].append(row)
        task_differences: dict[tuple[int, str], list[float]] = collections.defaultdict(list)
        midpoint = initial_attempts / 2
        for (mode, stratum, _task_id), task_rows in by_task.items():
            early = [bool(row["verification"]["passed"]) for row in task_rows if int(row["attempt"]) < midpoint]
            late = [bool(row["verification"]["passed"]) for row in task_rows if int(row["attempt"]) >= midpoint]
            if early and late:
                task_differences[(mode, stratum)].append(mean(late) - mean(early))
        observed = mean(value for values in task_differences.values() for value in values)
        bootstrap = []
        for _ in range(bootstrap_repetitions):
            sampled = []
            for values in task_differences.values():
                sampled.extend(rng.choice(values) for _ in values)
            bootstrap.append(mean(sampled))
        interval = [percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)]
        trend_rows.append(
            {
                "model": model,
                "estimand": "late_minus_early_matched_success_probability",
                "initial_attempts_only": initial_attempts,
                "task_fixed_effect_difference": observed,
                "bootstrap_ci_95": interval,
                "no_significant_trend": interval[0] <= 0.0 <= interval[1],
            }
        )
    return hazard_rows, trend_rows


def confirmation_cell_censoring(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int, int], list[bool]] = collections.defaultdict(list)
    for row in rows:
        if row.get("design") != "four_term":
            continue
        z = int(row["z"]) if "z" in row else -1
        groups[(row["model"], row["condition"], int(row["mode"]), z)].append(
            bool(row.get("censored"))
        )
    return [
        {
            "model": model,
            "condition": condition,
            "mode": mode,
            "z": z,
            "trajectories": len(values),
            "censoring_rate": mean(values),
        }
        for (model, condition, mode, z), values in sorted(groups.items())
    ]


def confirmation_integrity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identifiers = [(str(row["model"]), str(row["trajectory_id"])) for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("confirmation contains duplicate model/trajectory identifiers")
    invalid = []
    for row in rows:
        success = bool(row.get("success"))
        censored = bool(row.get("censored"))
        total_slots = int(row["total_slots"])
        issued = [int(value) for value in row["issued"]]
        if success == censored or total_slots <= 0 or sum(issued) != total_slots:
            invalid.append((row["model"], row["trajectory_id"]))
    if invalid:
        raise ValueError(f"confirmation contains inconsistent trajectory rows: {invalid[:5]}")
    wrong_shard_wins = [
        (str(row["model"]), str(row["trajectory_id"]))
        for row in rows
        if bool(row.get("success")) and int(row["winning_shard"]) != int(row["mode"])
    ]
    return {
        "unique_model_trajectory_ids": len(identifiers),
        "wrong_shard_successes": len(wrong_shard_wins),
        "wrong_shard_success_examples": wrong_shard_wins[:5],
    }


def planned_share_audit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = collections.defaultdict(
        lambda: {"planned": [0, 0, 0], "expected": [0.0, 0.0, 0.0], "slots": 0}
    )
    for row in rows:
        planned = [int(value) for value in row["planned_issued"]]
        slots = sum(planned)
        group = groups[(row["model"], row["condition"])]
        group["slots"] += slots
        for shard in range(3):
            group["planned"][shard] += planned[shard]
            group["expected"][shard] += slots * float(row["q"][shard])
    return [
        {
            "model": model,
            "condition": condition,
            "slots": values["slots"],
            "max_absolute_planned_share_error": max(
                abs(actual - expected) / values["slots"]
                for actual, expected in zip(values["planned"], values["expected"])
            ),
        }
        for (model, condition), values in sorted(groups.items())
    ]


def inverse_share_cells(
    task_means: dict[tuple[str, str, int, int, str, str], float],
    rows: list[dict[str, Any]],
    sampled_tasks: dict[tuple[int, str], list[str]] | None = None,
) -> list[tuple[str, int, float, float]]:
    cells = trajectory_cells(task_means, sampled_tasks)
    q_by_cell = {
        (row["model"], row["condition"], int(row["mode"]), int(row.get("z", -1))): float(
            row["q_true"]
        )
        for row in rows
        if row.get("design") == "four_term" and row["condition"] != "baseline_prior"
    }
    return [
        (model, mode, q_by_cell[(model, condition, mode, z)], value)
        for (model, condition, mode, z), value in cells.items()
        if condition != "baseline_prior"
    ]


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


def shared_tasks(
    keys: Iterable[tuple[Any, ...]], task_index: int, mode_index: int, stratum_index: int
) -> dict[tuple[int, str], list[str]]:
    by_cell: dict[tuple[int, str], set[str]] = collections.defaultdict(set)
    for key in keys:
        by_cell[(int(key[mode_index]), str(key[stratum_index]))].add(str(key[task_index]))
    return {cell: sorted(task_ids) for cell, task_ids in by_cell.items()}


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
    parser.add_argument("--initial-calibration-attempts", type=int, default=64)
    parser.add_argument("--max-off-diagonal-hazard-ratio", type=float, default=0.02)
    parser.add_argument("--beta-lower", type=float, default=0.90)
    parser.add_argument("--beta-upper", type=float, default=1.10)
    parser.add_argument("--max-share-error", type=float, default=0.01)
    parser.add_argument("--min-practitioner-kendall-tau", type=float, default=0.80)
    parser.add_argument("--max-practitioner-oracle-regret", type=float, default=0.10)
    parser.add_argument("--min-selected-model-probability", type=float, default=0.80)
    parser.add_argument("--max-absolute-mean-residual", type=float, default=0.10)
    parser.add_argument("--max-residual-rms", type=float, default=0.15)
    parser.add_argument("--max-rms-upper-95", type=float, default=0.20)
    parser.add_argument("--max-censoring", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-output", type=Path)
    args = parser.parse_args()

    calibration_rows = load_jsonl(args.calibration)
    confirmation_rows = load_jsonl(args.confirmation)
    calibration_task_ids = {row["task_id"] for row in calibration_rows}
    confirmation_task_ids = {row["task_id"] for row in confirmation_rows}
    overlap = calibration_task_ids & confirmation_task_ids
    if overlap:
        raise SystemExit(f"calibration and confirmation task overlap: {sorted(overlap)[:5]}")
    task_scales = calibration_task_scales(calibration_rows)
    scales = focused_scales(task_scales)
    integrity = confirmation_integrity(confirmation_rows)
    task_means = trajectory_task_means(confirmation_rows)
    cells = trajectory_cells(task_means)
    hazard_rows, attempt_trends = calibration_diagnostics(
        calibration_rows,
        args.initial_calibration_attempts,
        args.bootstrap_repetitions,
        args.seed + 1,
    )
    censoring_cells = confirmation_cell_censoring(confirmation_rows)
    share_audit = planned_share_audit(confirmation_rows)
    inverse_cells = inverse_share_cells(task_means, confirmation_rows)
    inverse_beta = fixed_effect_slope(inverse_cells)
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

    calibration_ids = shared_tasks(task_scales, task_index=3, mode_index=1, stratum_index=2)
    confirmation_ids = shared_tasks(task_means, task_index=5, mode_index=2, stratum_index=4)
    rng = random.Random(args.seed)
    bootstrap_residuals: dict[tuple[str, float, str], list[float]] = collections.defaultdict(list)
    bootstrap_predicted_deltas: dict[tuple[str, float, str], list[float]] = collections.defaultdict(list)
    bootstrap_primary_rms = []
    bootstrap_inverse_betas = []
    term_names = ("unit_cost_nats", "competence_nats", "information_nats", "mismatch_nats")
    bootstrap_term_slopes: dict[str, list[float]] = collections.defaultdict(list)
    for _ in range(args.bootstrap_repetitions):
        sampled_calibration = {
            cell: [rng.choice(task_ids) for _ in task_ids]
            for cell, task_ids in calibration_ids.items()
        }
        sampled_confirmation = {
            cell: [rng.choice(task_ids) for _ in task_ids]
            for cell, task_ids in confirmation_ids.items()
        }
        sampled_scales = focused_scales(task_scales, sampled_calibration)
        sampled_cells = trajectory_cells(task_means, sampled_confirmation)
        bootstrap_inverse_betas.append(
            fixed_effect_slope(inverse_share_cells(task_means, confirmation_rows, sampled_confirmation))
        )
        primary_residuals = []
        sampled_result_rows = []
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
                bootstrap_predicted_deltas[(label, alpha, allocation)].append(
                    terms["predicted_delta_nats"]
                )
                sampled_result_rows.append({**terms, "residual_nats": residual})
                if label == "cross_model_primary":
                    primary_residuals.append(residual)
        bootstrap_primary_rms.append(math.sqrt(mean(value * value for value in primary_residuals)))
        for term_name in term_names:
            bootstrap_term_slopes[term_name].append(
                simple_slope(
                    (float(row[term_name]), float(row["residual_nats"]))
                    for row in sampled_result_rows
                )
            )

    for result in results:
        samples = bootstrap_residuals[(result["comparison"], result["alpha"], result["allocation"])]
        result["residual_ci_95_nats"] = [percentile(samples, 0.025), percentile(samples, 0.975)]

    primary = [result for result in results if result["comparison"] == "cross_model_primary"]
    primary_residuals = [float(result["residual_nats"]) for result in primary]
    primary_mean = mean(primary_residuals)
    primary_rms = math.sqrt(mean(value * value for value in primary_residuals))
    choice_rows = []
    for result in primary:
        predicted = float(result["predicted_delta_nats"])
        observed = float(result["observed_delta_nats"])
        predicted_model = args.deployed_model if predicted >= 0.0 else args.baseline_model
        oracle_model = args.deployed_model if observed >= 0.0 else args.baseline_model
        predicted_samples = bootstrap_predicted_deltas[
            (result["comparison"], result["alpha"], result["allocation"])
        ]
        probability = mean(
            (value >= 0.0) if predicted_model == args.deployed_model else (value < 0.0)
            for value in predicted_samples
        )
        choice_rows.append(
            {
                "alpha": result["alpha"],
                "allocation": result["allocation"],
                "predicted_model": predicted_model,
                "oracle_model": oracle_model,
                "agreement": predicted_model == oracle_model,
                "selected_model_bootstrap_probability": probability,
                "oracle_regret_fraction": (
                    0.0 if predicted_model == oracle_model else math.exp(abs(observed)) - 1.0
                ),
            }
        )
    practitioner_kendall_tau = mean(1.0 if row["agreement"] else -1.0 for row in choice_rows)
    max_practitioner_regret = max(row["oracle_regret_fraction"] for row in choice_rows)
    min_selection_probability = min(
        row["selected_model_bootstrap_probability"] for row in choice_rows
    )
    censoring_rate = sum(bool(row.get("censored")) for row in confirmation_rows) / len(confirmation_rows)
    max_cell_censoring = max(row["censoring_rate"] for row in censoring_cells)
    max_share_error = max(row["max_absolute_planned_share_error"] for row in share_audit)
    max_hazard_ratio = max(row["off_diagonal_to_matched_upper_95"] for row in hazard_rows)
    focused_mode_rates: dict[tuple[str, int], list[bool]] = collections.defaultdict(list)
    for row in calibration_rows:
        if row["relation"] == "matched" and int(row["attempt"]) < args.initial_calibration_attempts:
            focused_mode_rates[(row["model"], int(row["mode"]))].append(
                bool(row["verification"]["passed"])
            )
    focused_mode_rows = [
        {"model": model, "mode": mode, "pass_probability": mean(values), "trials": len(values)}
        for (model, mode), values in sorted(focused_mode_rates.items())
    ]
    inverse_beta_ci_90 = [
        percentile(bootstrap_inverse_betas, 0.05),
        percentile(bootstrap_inverse_betas, 0.95),
    ]
    raw_term_p_values = {}
    observed_term_slopes = {}
    for term_name in term_names:
        observed_term_slopes[term_name] = simple_slope(
            (float(result[term_name]), float(result["residual_nats"])) for result in results
        )
        samples = bootstrap_term_slopes[term_name]
        lower_tail = (1 + sum(value <= 0.0 for value in samples)) / (len(samples) + 1)
        upper_tail = (1 + sum(value >= 0.0 for value in samples)) / (len(samples) + 1)
        raw_term_p_values[term_name] = min(1.0, 2.0 * min(lower_tail, upper_tail))
    adjusted_term_p_values = holm_adjust(raw_term_p_values)
    residual_slope_diagnostics = [
        {
            "term": term_name,
            "slope": observed_term_slopes[term_name],
            "bootstrap_ci_95": [
                percentile(bootstrap_term_slopes[term_name], 0.025),
                percentile(bootstrap_term_slopes[term_name], 0.975),
            ],
            "bootstrap_two_sided_p": raw_term_p_values[term_name],
            "holm_adjusted_p": adjusted_term_p_values[term_name],
            "significant_after_holm": adjusted_term_p_values[term_name] < 0.05,
        }
        for term_name in term_names
    ]
    rms_upper = percentile(bootstrap_primary_rms, 0.95)
    gates = {
        "focused_regime_pass": min(row["pass_probability"] for row in focused_mode_rows) >= 0.05,
        "attempt_stationarity_pass": all(row["no_significant_trend"] for row in attempt_trends),
        "off_diagonal_hazard_pass": max_hazard_ratio <= args.max_off_diagonal_hazard_ratio,
        "confirmation_wrong_shard_success_pass": integrity["wrong_shard_successes"] == 0,
        "inverse_share_beta_pass": (
            inverse_beta_ci_90[0] >= args.beta_lower and inverse_beta_ci_90[1] <= args.beta_upper
        ),
        "planned_share_pass": max_share_error <= args.max_share_error,
        "mean_residual_pass": abs(primary_mean) <= args.max_absolute_mean_residual,
        "residual_rms_pass": primary_rms <= args.max_residual_rms,
        "rms_upper_95_pass": rms_upper <= args.max_rms_upper_95,
        "censoring_pass": max_cell_censoring <= args.max_censoring,
        "residual_slope_holm_pass": not any(
            row["significant_after_holm"] for row in residual_slope_diagnostics
        ),
        "practitioner_kendall_tau_pass": (
            practitioner_kendall_tau >= args.min_practitioner_kendall_tau
        ),
        "practitioner_oracle_regret_pass": (
            max_practitioner_regret <= args.max_practitioner_oracle_regret
        ),
        "selected_model_probability_pass": (
            min_selection_probability >= args.min_selected_model_probability
        ),
    }
    bootstrap_record = None
    if args.bootstrap_output is not None:
        bootstrap_document = {
            "schema_version": 1,
            "analysis": "held_out_four_term_cluster_bootstrap_draws",
            "seed": args.seed,
            "repetitions": args.bootstrap_repetitions,
            "primary_residual_rms_nats": bootstrap_primary_rms,
            "inverse_share_beta": bootstrap_inverse_betas,
            "residuals_nats": {
                f"{label}|alpha={alpha:.8f}|allocation={allocation}": values
                for (label, alpha, allocation), values in sorted(bootstrap_residuals.items())
            },
            "predicted_deltas_nats": {
                f"{label}|alpha={alpha:.8f}|allocation={allocation}": values
                for (label, alpha, allocation), values in sorted(
                    bootstrap_predicted_deltas.items()
                )
            },
            "residual_term_slopes": dict(bootstrap_term_slopes),
        }
        args.bootstrap_output.parent.mkdir(parents=True, exist_ok=True)
        args.bootstrap_output.write_text(
            json.dumps(bootstrap_document, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        bootstrap_record = {
            "path": str(args.bootstrap_output),
            "sha256": sha256_path(args.bootstrap_output),
            "repetitions": args.bootstrap_repetitions,
        }
    summary = {
        "schema_version": 1,
        "analysis": "held_out_four_term_closure",
        "evidence_status": "held_out_confirmation",
        "baseline_model": args.baseline_model,
        "deployed_model": args.deployed_model,
        "clock": cost_document["clock"],
        "costs": costs,
        "input_provenance": {
            "calibration": [
                {"path": str(path), "sha256": sha256_path(path)} for path in args.calibration
            ],
            "confirmation": [
                {"path": str(path), "sha256": sha256_path(path)} for path in args.confirmation
            ],
            "design_manifest": {
                "path": str(args.design_manifest),
                "sha256": sha256_path(args.design_manifest),
            },
            "costs": {"path": str(args.costs), "sha256": sha256_path(args.costs)},
        },
        "bootstrap_draws": bootstrap_record,
        "focused_scales": [
            {
                "model": model,
                "mode": mode,
                "geometric_mean_t0_slots": value,
                "estimand": "exp(mean_task_log_t0)",
            }
            for (model, mode), value in sorted(scales.items())
        ],
        "focused_mode_pass_probabilities": focused_mode_rows,
        "calibration_hazard_diagnostics": hazard_rows,
        "attempt_index_diagnostics": attempt_trends,
        "confirmation_trajectories": len(confirmation_rows),
        "confirmation_integrity": integrity,
        "censoring_rate": censoring_rate,
        "max_cell_censoring_rate": max_cell_censoring,
        "confirmation_censoring_cells": censoring_cells,
        "planned_share_audit": share_audit,
        "max_absolute_planned_share_error": max_share_error,
        "confirmation_inverse_share_beta": inverse_beta,
        "confirmation_inverse_share_beta_ci_90": inverse_beta_ci_90,
        "primary_weighted_mean_residual_nats": primary_mean,
        "primary_residual_rms_nats": primary_rms,
        "primary_residual_rms_upper_95_nats": rms_upper,
        "residual_slope_diagnostics": residual_slope_diagnostics,
        "practitioner_choice": choice_rows,
        "practitioner_kendall_tau": practitioner_kendall_tau,
        "max_practitioner_oracle_regret_fraction": max_practitioner_regret,
        "min_selected_model_bootstrap_probability": min_selection_probability,
        "results": results,
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "INCONCLUSIVE_OR_FALSIFIED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
