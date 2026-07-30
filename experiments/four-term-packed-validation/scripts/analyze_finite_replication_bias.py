#!/usr/bin/env python3
"""Diagnose finite-repetition bias in logged first-passage mean estimates."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from generate_sai3_schedule_design import PRIOR, allocation, channel_probability  # noqa: E402


def mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def rms(values: Iterable[float]) -> float:
    materialized = list(values)
    return math.sqrt(mean(value * value for value in materialized))


def simple_slope(points: Iterable[tuple[float, float]]) -> float:
    materialized = list(points)
    x_mean = mean(x for x, _ in materialized)
    y_mean = mean(y for _, y in materialized)
    denominator = sum((x - x_mean) ** 2 for x, _ in materialized)
    return sum((x - x_mean) * (y - y_mean) for x, y in materialized) / denominator


def expected_log_sample_mean_bias(
    success_probability: float,
    repetitions: int,
    tail_tolerance: float = 1e-12,
) -> float:
    """Return E[log(mean tau)] - log(E[tau]) for geometric first passage."""
    if not 0.0 < success_probability <= 1.0:
        raise ValueError("success_probability must lie in (0, 1]")
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")

    # If F is failures before `repetitions` successes, then
    # sum(tau_i) = F + repetitions and F is negative-binomial.
    failures = 0
    probability = success_probability**repetitions
    mass = probability
    expected_log = 0.0
    while 1.0 - mass > tail_tolerance:
        probability *= (
            (failures + repetitions) / (failures + 1) * (1.0 - success_probability)
        )
        failures += 1
        mass += probability
        expected_log += probability * math.log((failures + repetitions) / repetitions)
        if failures > 1_000_000:
            raise ArithmeticError("negative-binomial tail did not converge")
    return expected_log / mass + math.log(success_probability)


def baseline_bias(
    scales: dict[tuple[str, int], float], model: str, repetitions: int
) -> float:
    return sum(
        PRIOR[mode]
        * expected_log_sample_mean_bias(PRIOR[mode] / scales[(model, mode)], repetitions)
        for mode in range(3)
    )


def deployed_bias(
    scales: dict[tuple[str, int], float],
    model: str,
    alpha: float,
    allocation_name: str,
    repetitions: int,
) -> float:
    return sum(
        PRIOR[mode]
        * channel_probability(alpha, mode, z)
        * expected_log_sample_mean_bias(
            allocation(alpha, z, allocation_name)[mode] / scales[(model, mode)], repetitions
        )
        for mode in range(3)
        for z in range(3)
    )


def analyze(document: dict, repetitions: int) -> dict:
    scales = {
        (row["model"], int(row["mode"])): float(row["geometric_mean_t0_slots"])
        for row in document["focused_scales"]
    }
    rows = []
    for source in document["results"]:
        predicted_bias = baseline_bias(scales, source["baseline_model"], repetitions) - deployed_bias(
            scales,
            source["deployed_model"],
            float(source["alpha"]),
            source["allocation"],
            repetitions,
        )
        raw_residual = float(source["residual_nats"])
        rows.append(
            {
                "comparison": source["comparison"],
                "alpha": source["alpha"],
                "allocation": source["allocation"],
                "mismatch_nats": source["mismatch_nats"],
                "raw_residual_nats": raw_residual,
                "predicted_finite_replication_bias_nats": predicted_bias,
                "bias_adjusted_residual_nats": raw_residual - predicted_bias,
            }
        )

    raw_slope = simple_slope(
        (float(row["mismatch_nats"]), float(row["raw_residual_nats"])) for row in rows
    )
    predicted_slope = simple_slope(
        (
            float(row["mismatch_nats"]),
            float(row["predicted_finite_replication_bias_nats"]),
        )
        for row in rows
    )
    adjusted_slope = simple_slope(
        (float(row["mismatch_nats"]), float(row["bias_adjusted_residual_nats"]))
        for row in rows
    )
    primary = [row for row in rows if row["comparison"] == "cross_model_primary"]
    return {
        "schema_version": 1,
        "analysis": "finite_replication_log_mean_bias",
        "evidence_status": "posthoc_diagnostic_not_confirmatory",
        "source_analysis": str(document.get("analysis", "unknown")),
        "repetitions_per_task_cell": repetitions,
        "assumptions": [
            "geometric stationary first passage",
            "zero off-diagonal success",
            "model-mode geometric calibration scale represents task probabilities",
        ],
        "limitation": "Uses aggregate model-mode scales and does not replace the frozen primary estimator or gate.",
        "raw_mismatch_slope": raw_slope,
        "predicted_finite_replication_mismatch_slope": predicted_slope,
        "bias_adjusted_mismatch_slope": adjusted_slope,
        "fraction_raw_slope_explained": predicted_slope / raw_slope,
        "all_comparisons_raw_residual_rms_nats": rms(
            float(row["raw_residual_nats"]) for row in rows
        ),
        "all_comparisons_bias_adjusted_residual_rms_nats": rms(
            float(row["bias_adjusted_residual_nats"]) for row in rows
        ),
        "primary_bias_adjusted_mean_residual_nats": mean(
            float(row["bias_adjusted_residual_nats"]) for row in primary
        ),
        "primary_bias_adjusted_residual_rms_nats": rms(
            float(row["bias_adjusted_residual_nats"]) for row in primary
        ),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--repetitions-per-task-cell", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    document = json.loads(args.analysis.read_text(encoding="utf-8"))
    result = analyze(document, args.repetitions_per_task_cell)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
