#!/usr/bin/env python3
"""Analyze physical SAI-3 trajectories for the inverse-allocation law."""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def sample_shard(q: list[float], rng: random.Random) -> int:
    draw = rng.random()
    cumulative = 0.0
    for shard, share in enumerate(q):
        cumulative += share
        if draw < cumulative or shard == len(q) - 1:
            return shard
    raise AssertionError("unreachable")


def fixed_effect_slope(cells: Iterable[tuple[str, int, float, float]]) -> float:
    """Fit log T = group intercept + beta*(-log q)."""
    groups: dict[tuple[str, int], list[tuple[float, float]]] = collections.defaultdict(list)
    for model, mode, q_true, mean_slots in cells:
        groups[(model, mode)].append((-math.log(q_true), math.log(mean_slots)))
    numerator = 0.0
    denominator = 0.0
    for points in groups.values():
        x_mean = mean(point[0] for point in points)
        y_mean = mean(point[1] for point in points)
        numerator += sum((x - x_mean) * (y - y_mean) for x, y in points)
        denominator += sum((x - x_mean) ** 2 for x, _ in points)
    return numerator / denominator


def task_cell_means(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str, str, float], float]:
    groups: dict[tuple[str, int, str, str, float], list[float]] = collections.defaultdict(list)
    for row in rows:
        if row.get("design") != "inverse_share":
            continue
        value = float(row["total_slots"])
        if row.get("censored"):
            value += 1.0
        groups[
            (
                row["model"],
                int(row["mode"]),
                row.get("task_stratum", "unknown"),
                row["task_id"],
                float(row["q_true"]),
            )
        ].append(value)
    return {key: mean(values) for key, values in groups.items()}


def aggregate_cells(
    task_means: dict[tuple[str, int, str, str, float], float],
    sampled_tasks: dict[tuple[str, int, str], list[str]] | None = None,
) -> list[tuple[str, int, float, float]]:
    values: dict[tuple[str, int, float], list[float]] = collections.defaultdict(list)
    if sampled_tasks is None:
        for (model, mode, _stratum, _task_id, q_true), task_mean in task_means.items():
            values[(model, mode, q_true)].append(task_mean)
    else:
        for (model, mode, stratum), task_ids in sampled_tasks.items():
            q_values = sorted(
                {
                    q
                    for candidate_model, candidate_mode, candidate_stratum, _task, q in task_means
                    if candidate_model == model
                    and candidate_mode == mode
                    and candidate_stratum == stratum
                }
            )
            for task_id in task_ids:
                for q_true in q_values:
                    values[(model, mode, q_true)].append(
                        task_means[(model, mode, stratum, task_id, q_true)]
                    )
    return [(model, mode, q_true, mean(cell_values)) for (model, mode, q_true), cell_values in sorted(values.items())]


def bootstrap_slopes(
    task_means: dict[tuple[str, int, str, str, float], float], repetitions: int, seed: int
) -> tuple[list[float], dict[str, list[float]]]:
    task_ids: dict[tuple[str, int, str], list[str]] = collections.defaultdict(list)
    for model, mode, stratum, task_id, _q in task_means:
        if task_id not in task_ids[(model, mode, stratum)]:
            task_ids[(model, mode, stratum)].append(task_id)
    rng = random.Random(seed)
    pooled = []
    by_model: dict[str, list[float]] = collections.defaultdict(list)
    for _ in range(repetitions):
        sampled = {
            key: [rng.choice(ids) for _ in ids]
            for key, ids in task_ids.items()
        }
        cells = aggregate_cells(task_means, sampled)
        pooled.append(fixed_effect_slope(cells))
        for model in sorted({cell[0] for cell in cells}):
            by_model[model].append(fixed_effect_slope(cell for cell in cells if cell[0] == model))
    return pooled, by_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--beta-lower", type=float, default=0.90)
    parser.add_argument("--beta-upper", type=float, default=1.10)
    parser.add_argument("--max-censoring", type=float, default=0.05)
    parser.add_argument("--max-residual-rms", type=float, default=0.15)
    parser.add_argument("--max-share-error", type=float, default=0.01)
    parser.add_argument("--share-audit-slots", type=int, default=128)
    args = parser.parse_args()

    rows = []
    for path in args.inputs:
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    if not rows:
        raise SystemExit("no trajectories")

    task_means = task_cell_means(rows)
    cells = aggregate_cells(task_means)
    models = sorted({cell[0] for cell in cells})
    pooled_beta = fixed_effect_slope(cells)
    model_betas = {
        model: fixed_effect_slope(cell for cell in cells if cell[0] == model)
        for model in models
    }
    bootstrap_pooled, bootstrap_models = bootstrap_slopes(task_means, args.bootstrap_repetitions, args.seed)

    cell_rows = []
    residuals = []
    for model, mode, q_true, mean_slots in cells:
        focused = next(
            value
            for candidate_model, candidate_mode, candidate_q, value in cells
            if candidate_model == model and candidate_mode == mode and math.isclose(candidate_q, 1.0)
        )
        residual = math.log(mean_slots) - math.log(focused) + math.log(q_true)
        if not math.isclose(q_true, 1.0):
            residuals.append(residual)
        cell_rows.append(
            {
                "model": model,
                "mode": mode,
                "q_true": q_true,
                "mean_first_passage_slots": mean_slots,
                "focused_mean_slots": focused,
                "packed_log_residual_nats": residual,
            }
        )

    censoring_rate = sum(bool(row.get("censored")) for row in rows) / len(rows)
    off_diagonal_wins = sum(
        bool(row.get("success")) and int(row.get("winning_shard")) != int(row["mode"])
        for row in rows
    )
    share_groups: dict[tuple[str, float], dict[str, Any]] = collections.defaultdict(
        lambda: {"planned": [0, 0, 0], "expected": [0.0, 0.0, 0.0], "slots": 0}
    )
    for row in rows:
        group = share_groups[(row["model"], float(row["q_true"]))]
        q = [float(value) for value in row["q"]]
        rng = random.Random(int(row["schedule_seed"]))
        planned = [0, 0, 0]
        for _ in range(args.share_audit_slots):
            planned[sample_shard(q, rng)] += 1
        group["slots"] += args.share_audit_slots
        for shard in range(3):
            group["planned"][shard] += planned[shard]
            group["expected"][shard] += args.share_audit_slots * q[shard]
    share_audit = []
    for (model, q_true), group in sorted(share_groups.items()):
        errors = [
            abs(actual - expected) / group["slots"]
            for actual, expected in zip(group["planned"], group["expected"])
        ]
        share_audit.append(
            {
                "model": model,
                "q_true": q_true,
                "slots": group["slots"],
                "max_absolute_planned_share_error": max(errors),
            }
        )
    max_share_error = max(item["max_absolute_planned_share_error"] for item in share_audit)
    beta_ci_90 = [percentile(bootstrap_pooled, 0.05), percentile(bootstrap_pooled, 0.95)]
    beta_ci_95 = [percentile(bootstrap_pooled, 0.025), percentile(bootstrap_pooled, 0.975)]
    model_rows = []
    for model in models:
        interval_90 = [percentile(bootstrap_models[model], 0.05), percentile(bootstrap_models[model], 0.95)]
        interval_95 = [percentile(bootstrap_models[model], 0.025), percentile(bootstrap_models[model], 0.975)]
        model_rows.append(
            {
                "model": model,
                "beta": model_betas[model],
                "beta_ci_90": interval_90,
                "beta_ci_95": interval_95,
                "equivalence_pass": interval_90[0] >= args.beta_lower and interval_90[1] <= args.beta_upper,
            }
        )
    residual_rms = math.sqrt(mean(value * value for value in residuals))
    model_equivalence_pass = all(row["equivalence_pass"] for row in model_rows)
    summary = {
        "schema_version": 1,
        "analysis": "physical_iid_inverse_share",
        "trajectories": len(rows),
        "censoring_rate": censoring_rate,
        "off_diagonal_wins": off_diagonal_wins,
        "max_absolute_planned_share_error": max_share_error,
        "planned_share_audit": share_audit,
        "pooled_beta": pooled_beta,
        "pooled_beta_ci_90": beta_ci_90,
        "pooled_beta_ci_95": beta_ci_95,
        "packed_residual_mean_nats": mean(residuals),
        "packed_residual_rms_nats": residual_rms,
        "models": model_rows,
        "cells": cell_rows,
        "gates": {
            "beta_equivalence_interval": [args.beta_lower, args.beta_upper],
            "max_censoring": args.max_censoring,
            "pooled_beta_equivalence_pass": beta_ci_90[0] >= args.beta_lower and beta_ci_90[1] <= args.beta_upper,
            "model_beta_equivalence_pass": model_equivalence_pass,
            "censoring_pass": censoring_rate <= args.max_censoring,
            "residual_rms_pass": residual_rms <= args.max_residual_rms,
            "planned_share_pass": max_share_error <= args.max_share_error,
        },
    }
    summary["status"] = "PASS" if all(summary["gates"].values()) else "INCONCLUSIVE_OR_FALSIFIED"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
