#!/usr/bin/env python3
"""Evaluate the frozen high-repetition mismatch-slope follow-up."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PHYSICAL_GATES = (
    "attempt_stationarity_pass",
    "censoring_pass",
    "confirmation_wrong_shard_success_pass",
    "focused_regime_pass",
    "inverse_share_beta_pass",
    "off_diagonal_hazard_pass",
    "planned_share_pass",
)


def mismatch_diagnostic(document: dict) -> dict:
    return next(
        row for row in document["residual_slope_diagnostics"] if row["term"] == "mismatch_nats"
    )


def analyze(
    primary: dict,
    replication: dict,
    replication_bias: dict,
    attenuation_threshold: float,
) -> dict:
    primary_diagnostic = mismatch_diagnostic(primary)
    replication_diagnostic = mismatch_diagnostic(replication)
    primary_slope = float(primary_diagnostic["slope"])
    replication_slope = float(replication_diagnostic["slope"])
    replication_interval = [float(value) for value in replication_diagnostic["bootstrap_ci_95"]]
    physical_gate_results = {
        name: bool(replication["gates"].get(name, False)) for name in PHYSICAL_GATES
    }
    physical_gates_pass = all(physical_gate_results.values())
    attenuation_pass = replication_slope <= attenuation_threshold
    if not physical_gates_pass:
        status = "FOLLOWUP_INVALID_PHYSICAL_GATE_FAILURE"
    elif attenuation_pass:
        status = "SUPPORTS_FINITE_REPLICATION_MECHANISM"
    else:
        status = "SUPPORTS_PERSISTENT_MISMATCH_DEVIATION"

    return {
        "schema_version": 1,
        "analysis": "fresh_high_replication_mismatch_slope_attenuation",
        "evidence_status": "posthoc_fresh_task_replication",
        "status": status,
        "primary_repetitions_per_task_cell": 6,
        "replication_repetitions_per_task_cell": replication_bias[
            "repetitions_per_task_cell"
        ],
        "primary_mismatch_slope": primary_slope,
        "primary_mismatch_slope_ci_95": primary_diagnostic["bootstrap_ci_95"],
        "replication_mismatch_slope": replication_slope,
        "replication_mismatch_slope_ci_95": replication_interval,
        "replication_mismatch_slope_holm_adjusted_p": replication_diagnostic[
            "holm_adjusted_p"
        ],
        "attenuation_threshold_slope": attenuation_threshold,
        "attenuation_ratio": replication_slope / primary_slope,
        "attenuation_point_pass": attenuation_pass,
        "replication_ci_excludes_primary_point": not (
            replication_interval[0] <= primary_slope <= replication_interval[1]
        ),
        "predicted_finite_replication_mismatch_slope": replication_bias[
            "predicted_finite_replication_mismatch_slope"
        ],
        "bias_adjusted_replication_mismatch_slope": replication_bias[
            "bias_adjusted_mismatch_slope"
        ],
        "physical_gates": physical_gate_results,
        "physical_gates_pass": physical_gates_pass,
        "interpretation": (
            "Diagnostic follow-up only; it explains or localizes the frozen primary failure "
            "but cannot reverse the primary outcome."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--replication", type=Path, required=True)
    parser.add_argument("--replication-bias", type=Path, required=True)
    parser.add_argument("--attenuation-threshold", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = analyze(
        json.loads(args.primary.read_text(encoding="utf-8")),
        json.loads(args.replication.read_text(encoding="utf-8")),
        json.loads(args.replication_bias.read_text(encoding="utf-8")),
        args.attenuation_threshold,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
