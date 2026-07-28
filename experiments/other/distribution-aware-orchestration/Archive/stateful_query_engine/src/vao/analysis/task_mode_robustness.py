"""Estimate statistical robustness and sample-size needs for task-mode studies."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from vao.analysis.task_mode_decomposition import _filter_complete_models, load_attempt_records, summarize_attempts


Z_95 = 1.959963984540054


def wilson_interval(successes: int, trials: int, *, z: float = Z_95) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 1.0)
    phat = successes / trials
    denom = 1.0 + (z * z) / trials
    center = (phat + (z * z) / (2.0 * trials)) / denom
    margin = (z / denom) * math.sqrt((phat * (1.0 - phat) / trials) + ((z * z) / (4.0 * trials * trials)))
    return (max(0.0, center - margin), min(1.0, center + margin))


def required_trials_for_wilson_half_width(phat: float, target_half_width: float, *, z: float = Z_95, max_trials: int = 100000) -> int:
    phat = min(max(float(phat), 1e-6), 1.0 - 1e-6)
    if target_half_width <= 0:
        return 1
    for trials in range(1, max_trials + 1):
        lo, hi = wilson_interval(round(phat * trials), trials, z=z)
        if (hi - lo) / 2.0 <= target_half_width:
            return trials
    return max_trials


def bernstein_bound_runs(mode_count: int, *, p_min: float, delta_acc: float, delta_conf: float) -> float:
    return 3.0 * math.log((2.0 * mode_count) / delta_conf) / (delta_acc * delta_acc * p_min)


def hoeffding_bound_runs(mode_count: int, *, p_min: float, delta_acc: float, delta_conf: float) -> float:
    return math.log((2.0 * mode_count) / delta_conf) / (2.0 * delta_acc * delta_acc * p_min * p_min)


def analyze_robustness(
    roots: list[Path],
    *,
    out_dir: Path,
    success_threshold: float,
    success_mode: str,
    improvement_threshold: float,
    pilot_split: str,
    holdout_split: str,
    target_half_width: float,
    delta_acc: float,
    delta_conf: float,
) -> dict[str, Any]:
    attempts = load_attempt_records(
        roots,
        success_threshold=success_threshold,
        success_mode=success_mode,
        improvement_threshold=improvement_threshold,
    )
    summary = summarize_attempts(attempts, cost_metric="wall_seconds")
    summary = _filter_complete_models(summary, pilot_split=pilot_split, holdout_split=holdout_split)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[Any]] = {}
    for record in attempts:
        grouped.setdefault((record.split, record.task_mode_true, record.model_id), []).append(record)

    filtered_keys = {
        (str(row["split"]), str(row["task_mode_true"]), str(row["model_id"]))
        for _, row in summary.iterrows()
    }

    smoothed_probs: list[float] = []
    for key, items in sorted(grouped.items()):
        if key not in filtered_keys:
            continue
        successes = sum(1 for item in items if item.success)
        trials = len(items)
        lo, hi = wilson_interval(successes, trials)
        phat = successes / trials if trials else 0.0
        smoothed = (successes + 1.0) / (trials + 2.0)
        smoothed_probs.append(smoothed)
        required = required_trials_for_wilson_half_width(phat if 0.0 < phat < 1.0 else smoothed, target_half_width)
        rows.append(
            {
                "split": key[0],
                "task_mode_true": key[1],
                "model_id": key[2],
                "trials": trials,
                "successes": successes,
                "success_prob": phat,
                "wilson_low": lo,
                "wilson_high": hi,
                "wilson_half_width": (hi - lo) / 2.0,
                "smoothed_success_prob": smoothed,
                "target_half_width": target_half_width,
                "required_trials_for_target_half_width": required,
                "additional_trials_needed": max(0, required - trials),
            }
        )

    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "robustness_by_cell.csv", index=False)

    task_modes = sorted(frame["task_mode_true"].unique())
    mode_count = max(len(task_modes), 1)
    p_min_smooth = min(smoothed_probs) if smoothed_probs else 1e-6
    bernstein = bernstein_bound_runs(mode_count, p_min=p_min_smooth, delta_acc=delta_acc, delta_conf=delta_conf)
    hoeffding = hoeffding_bound_runs(mode_count, p_min=p_min_smooth, delta_acc=delta_acc, delta_conf=delta_conf)
    result = {
        "success_mode": success_mode,
        "success_threshold": success_threshold,
        "improvement_threshold": improvement_threshold,
        "target_half_width": target_half_width,
        "delta_acc": delta_acc,
        "delta_conf": delta_conf,
        "mode_count": mode_count,
        "p_min_smoothed": p_min_smooth,
        "bernstein_runs_per_mode": bernstein,
        "hoeffding_runs_per_mode": hoeffding,
        "max_additional_trials_needed_any_cell": int(frame["additional_trials_needed"].max()) if not frame.empty else 0,
        "cells": rows,
    }
    (out_dir / "robustness_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_report(result, out_dir / "report.md")
    return result


def _write_report(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# Task-Mode Robustness",
        "",
        f"- Success mode: `{result['success_mode']}`",
        f"- Success threshold: `{result['success_threshold']}`",
        f"- Improvement threshold: `{result['improvement_threshold']}`",
        f"- Target Wilson half-width: `{result['target_half_width']}`",
        f"- Smoothed p_min: `{result['p_min_smoothed']:.6f}`",
        f"- Bernstein per-mode target: `{result['bernstein_runs_per_mode']:.2f}`",
        f"- Hoeffding per-mode target: `{result['hoeffding_runs_per_mode']:.2f}`",
        f"- Max additional trials needed in any current cell: `{result['max_additional_trials_needed_any_cell']}`",
        "",
        "## Current Cells",
        "",
    ]
    for cell in result["cells"]:
        lines.append(
            f"- `{cell['split']} / {cell['task_mode_true']} / {cell['model_id']}`: "
            f"`{cell['successes']}/{cell['trials']}` successes, "
            f"Wilson=`[{cell['wilson_low']:.3f}, {cell['wilson_high']:.3f}]`, "
            f"additional-for-target=`{cell['additional_trials_needed']}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--success-threshold", type=float, default=0.95)
    parser.add_argument("--success-mode", choices=["absolute_loss", "relative_improvement"], default="relative_improvement")
    parser.add_argument("--improvement-threshold", type=float, default=0.05)
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument("--target-half-width", type=float, default=0.15)
    parser.add_argument("--delta-acc", type=float, default=0.25)
    parser.add_argument("--delta-conf", type=float, default=0.05)
    args = parser.parse_args(argv)
    result = analyze_robustness(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        success_threshold=args.success_threshold,
        success_mode=args.success_mode,
        improvement_threshold=args.improvement_threshold,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        target_half_width=args.target_half_width,
        delta_acc=args.delta_acc,
        delta_conf=args.delta_conf,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
