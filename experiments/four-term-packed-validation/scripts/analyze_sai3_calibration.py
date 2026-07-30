#!/usr/bin/env python3
"""Audit frozen SAI-3 calibration completions before confirmation."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_sai3_four_term import calibration_diagnostics, load_jsonl, mean  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--initial-matched-attempts", type=int, default=64)
    parser.add_argument("--wrong-attempts-per-shard", type=int, default=4)
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--min-focused-probability", type=float, default=0.05)
    parser.add_argument("--max-off-diagonal-hazard-ratio", type=float, default=0.02)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = load_jsonl(args.inputs)
    if not rows:
        raise SystemExit("no calibration completions")
    physical_keys = [
        (row["model"], row["task_id"], int(row["shard"]), int(row["attempt"]))
        for row in rows
    ]
    duplicate_slots = len(physical_keys) - len(set(physical_keys))
    duplicate_seeds = len(rows) - len({(row["model"], int(row["seed"])) for row in rows})

    task_groups: dict[tuple[str, int, str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        task_groups[
            (row["model"], int(row["mode"]), row["task_stratum"], row["task_id"])
        ].append(row)
    task_rows = []
    for (model, mode, stratum, task_id), task_completions in sorted(task_groups.items()):
        matched = [row for row in task_completions if row["relation"] == "matched"]
        wrong = [row for row in task_completions if row["relation"] == "wrong"]
        task_rows.append(
            {
                "model": model,
                "mode": mode,
                "task_stratum": stratum,
                "task_id": task_id,
                "matched_trials": len(matched),
                "matched_successes": sum(bool(row["verification"]["passed"]) for row in matched),
                "initial_matched_successes": sum(
                    bool(row["verification"]["passed"])
                    for row in matched
                    if int(row["attempt"]) < args.initial_matched_attempts
                ),
                "wrong_trials": len(wrong),
                "wrong_trials_by_shard": dict(
                    sorted(collections.Counter(int(row["shard"]) for row in wrong).items())
                ),
                "wrong_successes": sum(bool(row["verification"]["passed"]) for row in wrong),
            }
        )

    focused_groups: dict[tuple[str, int], list[bool]] = collections.defaultdict(list)
    for row in rows:
        if row["relation"] == "matched" and int(row["attempt"]) < args.initial_matched_attempts:
            focused_groups[(row["model"], int(row["mode"]))].append(
                bool(row["verification"]["passed"])
            )
    focused_rates = [
        {"model": model, "mode": mode, "trials": len(values), "pass_probability": mean(values)}
        for (model, mode), values in sorted(focused_groups.items())
    ]
    hazard_rows, attempt_rows = calibration_diagnostics(
        rows,
        args.initial_matched_attempts,
        args.bootstrap_repetitions,
        args.seed,
    )
    zero_cells = [row for row in task_rows if row["matched_successes"] == 0]
    expected_wrong_trials = 2 * args.wrong_attempts_per_shard
    count_mismatches = [
        row
        for row in task_rows
        if not (
            row["matched_trials"] == args.initial_matched_attempts
            or (
                row["matched_trials"] == 2 * args.initial_matched_attempts
                and row["initial_matched_successes"] == 0
            )
        )
        or row["wrong_trials"] != expected_wrong_trials
        or sorted(row["wrong_trials_by_shard"].values())
        != [args.wrong_attempts_per_shard, args.wrong_attempts_per_shard]
        or int(row["mode"]) in row["wrong_trials_by_shard"]
    ]
    max_hazard_ratio = max(row["off_diagonal_to_matched_upper_95"] for row in hazard_rows)
    gates = {
        "unique_physical_slots_pass": duplicate_slots == 0 and duplicate_seeds == 0,
        "completion_counts_pass": not count_mismatches,
        "focused_identification_pass": not zero_cells,
        "focused_regime_pass": min(row["pass_probability"] for row in focused_rates)
        >= args.min_focused_probability,
        "off_diagonal_hazard_pass": max_hazard_ratio <= args.max_off_diagonal_hazard_ratio,
        "attempt_stationarity_pass": all(row["no_significant_trend"] for row in attempt_rows),
    }
    summary = {
        "schema_version": 1,
        "analysis": "frozen_calibration_gate",
        "evidence_status": "calibration_not_confirmation",
        "completions": len(rows),
        "models": sorted({row["model"] for row in rows}),
        "tasks": len(task_rows),
        "duplicate_physical_slots": duplicate_slots,
        "duplicate_model_seeds": duplicate_seeds,
        "zero_success_task_cells": len(zero_cells),
        "count_mismatch_task_cells": len(count_mismatches),
        "focused_rates": focused_rates,
        "hazard_diagnostics": hazard_rows,
        "attempt_index_diagnostics": attempt_rows,
        "gates": gates,
        "status": "PASS" if all(gates.values()) else "INCONCLUSIVE_OR_FALSIFIED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
