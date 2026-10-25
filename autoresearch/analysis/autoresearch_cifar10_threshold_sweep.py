"""Sweep relative success thresholds and derive induced entry/occupancy statistics.

This script calibrates the theorem-facing binary verifier for AutoResearch runs.
A threshold ``delta`` induces a first-passage time ``tau``: the first trajectory
step at which the best visible validation loss improves over baseline by at
least ``delta`` in relative terms. Alongside that theorem-facing entry metric,
the script also reports occupancy-style diagnostics based on how often the
selected trajectory stays above threshold over the full horizon.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vao.success_metrics import first_success_step, relative_improvement, validate_relative_threshold


@dataclass(frozen=True)
class RunTrace:
    run_dir: Path
    run_id: str
    split: str
    model_alias: str
    model_id: str
    task_mode_true: str | None
    baseline_loss: float
    final_best_visible_loss: float | None
    selected_loss_by_step: list[float | None]
    best_visible_by_step: list[float | None]


def _parse_thresholds(raw: str) -> list[float]:
    values = [validate_relative_threshold(float(item.strip())) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("no thresholds provided")
    return sorted(dict.fromkeys(values))


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_traces(roots: list[Path]) -> list[RunTrace]:
    traces: list[RunTrace] = []
    for root in roots:
        for summary_path in sorted(root.glob("**/run_summary.json")):
            run_dir = summary_path.parent
            manifest_path = run_dir / "run_manifest.json"
            evals_path = run_dir / "evaluations.jsonl"
            if not manifest_path.exists() or not evals_path.exists():
                continue
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            baseline_loss = float(summary.get("baseline_loss") or float("inf"))
            running_best = baseline_loss if baseline_loss > 0 else float("inf")
            selected_loss_by_step: list[float | None] = []
            best_visible_by_step: list[float | None] = []
            for line in evals_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                selected_losses = [
                    float(branch.get("latent_loss"))
                    for branch in (record.get("branches") or [])
                    if branch.get("promoted_as_parent") and branch.get("correctness")
                ]
                selected_loss_by_step.append(min(selected_losses) if selected_losses else None)
                if selected_losses:
                    running_best = min(running_best, min(selected_losses))
                best_visible_by_step.append(running_best if running_best != float("inf") else None)
            traces.append(
                RunTrace(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or run_dir.name),
                    split=str(manifest.get("task_mode_split") or "unspecified"),
                    model_alias=str(manifest.get("model_alias") or summary.get("model_alias") or summary.get("model_id") or "unknown_model"),
                    model_id=str(summary.get("model_id") or manifest.get("model_id") or "unknown_model"),
                    task_mode_true=manifest.get("task_mode_true"),
                    baseline_loss=baseline_loss,
                    final_best_visible_loss=_coerce_float(summary.get("best_visible_loss")),
                    selected_loss_by_step=selected_loss_by_step,
                    best_visible_by_step=best_visible_by_step,
                )
            )
    return traces


def _summarize_group(traces: list[RunTrace], threshold: float) -> dict[str, Any]:
    threshold = validate_relative_threshold(threshold)
    tau_values = [
        first_success_step(trace.baseline_loss, trace.best_visible_by_step, threshold=threshold)
        for trace in traces
    ]
    successes = [tau for tau in tau_values if tau is not None]
    rel_improvements = [relative_improvement(trace.baseline_loss, trace.final_best_visible_loss) for trace in traces]
    selected_hit_counts = []
    selected_hit_rates = []
    best_hit_counts = []
    mean_selected_rel = []
    mean_best_rel = []
    for trace in traces:
        selected_rels = [relative_improvement(trace.baseline_loss, loss) for loss in trace.selected_loss_by_step]
        best_rels = [relative_improvement(trace.baseline_loss, loss) for loss in trace.best_visible_by_step]
        if selected_rels:
            mean_selected_rel.append(statistics.fmean(selected_rels))
            selected_hits = sum(1 for value in selected_rels if value >= threshold)
            selected_hit_counts.append(selected_hits)
            selected_hit_rates.append(selected_hits / len(selected_rels))
        if best_rels:
            mean_best_rel.append(statistics.fmean(best_rels))
            best_hits = sum(1 for value in best_rels if value >= threshold)
            best_hit_counts.append(best_hits)
    return {
        "attempt_count": len(traces),
        "success_prob": (len(successes) / len(traces)) if traces else 0.0,
        "entry_success_prob": (len(successes) / len(traces)) if traces else 0.0,
        "median_tau": statistics.median(successes) if successes else None,
        "mean_tau": statistics.fmean(successes) if successes else None,
        "mean_final_relative_improvement": statistics.fmean(rel_improvements) if rel_improvements else 0.0,
        "mean_selected_hit_count": statistics.fmean(selected_hit_counts) if selected_hit_counts else 0.0,
        "mean_selected_hit_rate": statistics.fmean(selected_hit_rates) if selected_hit_rates else 0.0,
        "mean_selected_threshold_hit_count": statistics.fmean(selected_hit_counts) if selected_hit_counts else 0.0,
        "mean_selected_threshold_occupancy": statistics.fmean(selected_hit_rates) if selected_hit_rates else 0.0,
        "mean_best_hit_count": statistics.fmean(best_hit_counts) if best_hit_counts else 0.0,
        "mean_best_threshold_hit_count": statistics.fmean(best_hit_counts) if best_hit_counts else 0.0,
        "mean_selected_relative_improvement_over_steps": statistics.fmean(mean_selected_rel) if mean_selected_rel else 0.0,
        "mean_best_relative_improvement_over_steps": statistics.fmean(mean_best_rel) if mean_best_rel else 0.0,
    }


def analyze_thresholds(traces: list[RunTrace], thresholds: list[float]) -> dict[str, Any]:
    overall: list[dict[str, Any]] = []
    by_model: list[dict[str, Any]] = []
    by_mode: list[dict[str, Any]] = []
    by_model_mode: list[dict[str, Any]] = []
    for threshold in thresholds:
        overall.append({"threshold": threshold, **_summarize_group(traces, threshold)})

        model_groups: dict[str, list[RunTrace]] = defaultdict(list)
        mode_groups: dict[str, list[RunTrace]] = defaultdict(list)
        model_mode_groups: dict[tuple[str, str], list[RunTrace]] = defaultdict(list)
        for trace in traces:
            model_groups[trace.model_alias].append(trace)
            if trace.task_mode_true:
                mode_groups[str(trace.task_mode_true)].append(trace)
                model_mode_groups[(trace.model_alias, str(trace.task_mode_true))].append(trace)
        for model_alias, items in sorted(model_groups.items()):
            by_model.append({"threshold": threshold, "model_alias": model_alias, **_summarize_group(items, threshold)})
        for task_mode_true, items in sorted(mode_groups.items()):
            by_mode.append({"threshold": threshold, "task_mode_true": task_mode_true, **_summarize_group(items, threshold)})
        for (model_alias, task_mode_true), items in sorted(model_mode_groups.items()):
            by_model_mode.append(
                {
                    "threshold": threshold,
                    "model_alias": model_alias,
                    "task_mode_true": task_mode_true,
                    **_summarize_group(items, threshold),
                }
            )
    return {
        "run_count": len(traces),
        "thresholds": thresholds,
        "overall": overall,
        "by_model": by_model,
        "by_mode": by_mode,
        "by_model_mode": by_model_mode,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Run roots containing AutoResearch run_summary.json files")
    parser.add_argument("--thresholds", default="0.01,0.02,0.05,0.10,0.15")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    traces = _load_traces([Path(item) for item in args.roots])
    payload = analyze_thresholds(traces, _parse_thresholds(args.thresholds))
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
