"""Compare Phase 3 replacement-file runs with Phase 3.5 patch-based runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


METRICS = [
    "average_wall_clock_seconds_per_step",
    "average_agent_cost_usd_per_step",
    "parse_failure_rate",
    "code_validation_failure_rate",
    "verifier_failure_rate",
    "correctness_rate_by_mode",
    "average_gain_by_mode",
    "mean_routing_regret",
    "best_visible_loss",
    "best_counterfactual_loss",
]


def compare(replacement_summary: dict[str, Any], patch_summary: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in METRICS:
        old_value = replacement_summary.get(key)
        new_value = patch_summary.get(key)
        metrics[key] = {
            "phase3_replacement": old_value,
            "phase35_patch": new_value,
            "delta": _delta(new_value, old_value),
            "ratio_patch_over_replacement": _ratio(new_value, old_value),
        }
    return {
        "phase3_replacement": {
            "run_count": replacement_summary.get("run_count"),
            "step_count": replacement_summary.get("step_count"),
            "branch_evaluation_count": replacement_summary.get("branch_evaluation_count"),
        },
        "phase35_patch": {
            "run_count": patch_summary.get("run_count"),
            "step_count": patch_summary.get("step_count"),
            "branch_evaluation_count": patch_summary.get("branch_evaluation_count"),
        },
        "metrics": metrics,
    }


def _delta(new_value: Any, old_value: Any) -> Any:
    if isinstance(new_value, int | float) and isinstance(old_value, int | float):
        return float(new_value) - float(old_value)
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        keys = sorted(set(new_value) | set(old_value))
        return {key: _delta(new_value.get(key), old_value.get(key)) for key in keys}
    return None


def _ratio(new_value: Any, old_value: Any) -> Any:
    if isinstance(new_value, int | float) and isinstance(old_value, int | float) and float(old_value) != 0.0:
        return float(new_value) / float(old_value)
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        keys = sorted(set(new_value) | set(old_value))
        return {key: _ratio(new_value.get(key), old_value.get(key)) for key in keys}
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replacement_summary", required=True)
    parser.add_argument("--patch_summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    replacement = json.loads(Path(args.replacement_summary).read_text(encoding="utf-8"))
    patch = json.loads(Path(args.patch_summary).read_text(encoding="utf-8"))
    result = compare(replacement, patch)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
