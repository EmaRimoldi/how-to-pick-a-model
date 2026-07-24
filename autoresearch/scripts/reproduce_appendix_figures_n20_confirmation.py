"""Reproduce appendix AutoResearch figures from official n=20 confirmation runs.

This script uses only the raw runs listed as present in
experiments/autoresearch/05_autoresearch_model_routing/raw/manifests/
balanced_n30_raw_coverage.csv. Those are the 20 official confirmation trials per
mode-worker cell; missing pilot trials are intentionally excluded.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from autoresearch.scripts import analyze_autoresearch_threeworker_final as analysis
from autoresearch.scripts import plot_autoresearch_certified_resource as certified


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_ROOT = (
    REPO_ROOT / "experiments" / "autoresearch" / "05_autoresearch_model_routing"
)
DEFAULT_OUT_DIR = DEFAULT_EXPERIMENT_ROOT / "results" / "figures_n20_confirmation"
DEFAULT_ACCOUNTING_DIR = DEFAULT_EXPERIMENT_ROOT / "results" / "accounting_n20_confirmation"
DEFAULT_ROUTER_ANALYSIS = DEFAULT_EXPERIMENT_ROOT / "results" / "accounting" / "threeworker_final_analysis.json"
DEFAULT_Z_ABLATION = DEFAULT_EXPERIMENT_ROOT / "results" / "accounting" / "z_signal_ablation_partial.json"
APPENDIX_FIGURE_STEMS = {
    "quality_vs_certified_resource",
    "first_hit_ecdf_by_mode",
    "deployment_mix_sensitivity",
    "threeworker_deployment_frontier",
    "threeworker_negative_controls",
    "threeworker_threshold_sensitivity",
    "threeworker_improvement_distribution",
    "threeworker_tau_distribution",
    "threeworker_relative_improvement_trajectories",
    "threeworker_worker_cost_quality_diagnostics",
    "threeworker_cost_to_tau_by_mode_worker",
    "diag_z_signal_ablation",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    rows.sort(key=lambda row: int(row.get("step") or 0))
    return rows


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def selected_loss(row: dict[str, Any]) -> float | None:
    selected = next((branch for branch in row.get("branches", []) if branch.get("promoted_as_parent")), None)
    if selected is None:
        selected = next((branch for branch in row.get("branches", []) if branch.get("selected_as_visible")), None)
    if selected and selected.get("correctness") and selected.get("latent_loss") is not None:
        loss = safe_float(selected["latent_loss"])
        return loss if math.isfinite(loss) else None
    return None


def selected_loss_by_step(rows: list[dict[str, Any]]) -> list[float | None]:
    return [selected_loss(row) for row in rows]


def best_visible_by_step(baseline: float, rows: list[dict[str, Any]], selected_losses: list[float | None]) -> list[float | None]:
    values: list[float | None] = []
    running = baseline if math.isfinite(baseline) and baseline > 0 else math.inf
    for row, loss in zip(rows, selected_losses):
        direct = safe_float(row.get("best_visible_so_far"))
        if math.isfinite(direct):
            running = direct
        elif loss is not None:
            running = min(running, loss)
        values.append(running if math.isfinite(running) else None)
    return values


def total_tokens(rows: list[dict[str, Any]]) -> int:
    return sum(int(row.get("total_tokens") or 0) for row in rows)


def record_from_run(run_dir: Path, trial_id: str) -> dict[str, Any] | None:
    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "run_summary.json"
    eval_path = run_dir / "evaluations.jsonl"
    if not manifest_path.exists() or not summary_path.exists() or not eval_path.exists():
        return None

    manifest = load_json(manifest_path)
    summary = load_json(summary_path)
    eval_rows = load_jsonl(eval_path)
    mode = str(manifest.get("task_mode_true") or "")
    worker = str(manifest.get("model_alias") or "")
    seed = manifest.get("instance_seed")
    if mode not in analysis.MODES or worker not in analysis.WORKERS or seed is None:
        return None

    baseline = safe_float(summary.get("baseline_loss"))
    best_loss = safe_float(summary.get("best_visible_loss"))
    best_loss = best_loss if math.isfinite(best_loss) else None
    selected_losses = selected_loss_by_step(eval_rows)
    best_losses = best_visible_by_step(baseline, eval_rows, selected_losses)
    final_loss = selected_losses[-1] if selected_losses and selected_losses[-1] is not None else best_loss
    tau_step = analysis.first_hit_step(baseline, best_losses, analysis.THRESHOLD)
    occupancy = analysis.threshold_occupancy_from_losses(baseline, selected_losses, analysis.THRESHOLD)

    return {
        "run_dir": str(run_dir),
        "run_id": str(summary.get("run_id") or run_dir.name),
        "completed_at": str(summary.get("completed_at") or ""),
        "split": "holdout",
        "trial_id": trial_id,
        "mode": mode,
        "worker": worker,
        "seed": int(seed),
        "baseline_loss": baseline,
        "best_loss": best_loss,
        "final_loss": final_loss,
        "success": tau_step is not None,
        "tau_step": tau_step,
        "steps_completed": int(summary.get("steps_completed") or len(eval_rows) or 0),
        "elapsed_wall_seconds": safe_float(summary.get("elapsed_wall_seconds"), 0.0),
        "total_tokens": total_tokens(eval_rows),
        "threshold_occupancy": occupancy,
        "final_relative_improvement": analysis.rel_improvement(baseline, final_loss),
        "selected_losses_by_step": selected_losses,
        "best_losses_by_step": best_losses,
    }


def load_confirmation_rows(experiment_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_path = experiment_root / "raw" / "manifests" / "balanced_n30_raw_coverage.csv"
    raw_root = experiment_root / "raw"
    rows: list[dict[str, Any]] = []
    selection: dict[str, Any] = {
        "source_manifest": str(manifest_path),
        "selection": "raw_status == present",
        "cells": {},
    }
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        for item in csv.DictReader(handle):
            if item.get("raw_status") != "present":
                continue
            local_raw_dir = item.get("local_raw_dir") or ""
            run_dir = (experiment_root / local_raw_dir).resolve() if local_raw_dir.startswith("raw/") else (raw_root / local_raw_dir).resolve()
            record = record_from_run(run_dir, item["trial_id"])
            if record is None:
                raise RuntimeError(f"Unable to load present run: {run_dir}")
            rows.append(record)

    for mode in analysis.MODES:
        for worker in analysis.WORKERS:
            cell = sorted(
                [row for row in rows if row["mode"] == mode and row["worker"] == worker],
                key=lambda row: row["seed"],
            )
            selection["cells"][f"{mode}/{worker}"] = {
                "selected": len(cell),
                "trial_ids": [row["trial_id"] for row in cell],
                "seeds": [row["seed"] for row in cell],
            }
    return rows, selection


def rebuild_router_from_processed(
    path: Path,
    frontier: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    lambda_wall: float,
) -> dict[str, Any]:
    if not path.exists():
        return {"available": False}
    payload = load_json(path)
    processed = ((payload.get("router") or {}).get("rows") or [])
    if not processed:
        return {"available": False}

    mode_worker_loss = {
        (row["mode"], row["worker"]): row["deployment_loss_ci"]["mean"]
        for row in frontier
    }
    score = {(row["mode"], row["worker"]): row["log_effort_objective"] for row in frontier}
    best_score = {mode: min(score[(mode, worker)] for worker in analysis.WORKERS) for mode in analysis.MODES}

    clean_rows = []
    for row in processed:
        mode = row.get("mode")
        worker = row.get("worker")
        if mode not in analysis.MODES or worker not in analysis.WORKERS:
            continue
        clean_rows.append(
            {
                "mode": mode,
                "seed": int(row.get("seed")),
                "signal": row.get("signal"),
                "control": row.get("control"),
                "worker": worker,
                "confidence": row.get("confidence"),
                "measurement_loss": safe_float(row.get("measurement_loss"), 0.0),
            }
        )

    selection_summary = []
    by_signal_control: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in clean_rows:
        by_signal_control[(row["signal"], row["control"])].append(row)
    for (signal, control), items in sorted(by_signal_control.items()):
        counts = Counter(row["worker"] for row in items)
        regrets = [score[(row["mode"], row["worker"])] - best_score[row["mode"]] for row in items]
        selection_summary.append(
            {
                "signal": signal,
                "control": control,
                "records": len(items),
                "selected": dict(counts),
                "mean_log_effort_regret": analysis.fmean(regrets) if regrets else None,
            }
        )

    by_key = {(row["mode"], row["seed"], row["control"], row["signal"]): row for row in clean_rows}
    gain_rows = []
    for row in clean_rows:
        if row["signal"] == "Z0":
            continue
        base = by_key.get((row["mode"], row["seed"], row["control"], "Z0"))
        if base is None:
            continue
        base_loss = mode_worker_loss[(base["mode"], base["worker"])]
        routed_loss = mode_worker_loss[(row["mode"], row["worker"])]
        gain_rows.append(
            {
                "mode": row["mode"],
                "seed": row["seed"],
                "control": row["control"],
                "signal": row["signal"],
                "z0_worker": base["worker"],
                "zj_worker": row["worker"],
                "shift": base["worker"] != row["worker"],
                "gross_gain": base_loss - routed_loss,
                "measurement_loss": row["measurement_loss"],
                "net_gain": base_loss - routed_loss - row["measurement_loss"],
            }
        )

    gain_summary = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in gain_rows:
        grouped[(row["signal"], row["control"])].append(row)
    for (signal, control), items in sorted(grouped.items()):
        gains = [row["net_gain"] for row in items]
        gain_summary.append(
            {
                "signal": signal,
                "control": control,
                "pairs": len(items),
                "shift_rate": analysis.fmean(1.0 if row["shift"] else 0.0 for row in items),
                "net_gain_ci": analysis.bootstrap_ci(gains),
                "gross_gain_mean": analysis.fmean(row["gross_gain"] for row in items),
                "measurement_loss_mean": analysis.fmean(row["measurement_loss"] for row in items),
                "loss_increasing_shift_count": sum(1 for row in items if row["shift"] and row["net_gain"] < 0),
            }
        )

    return {
        "available": True,
        "router_path": str(path),
        "records": len(clean_rows),
        "rows": clean_rows,
        "frontier": frontier,
        "selection_summary": selection_summary,
        "gain_summary": gain_summary,
        "gain_rows": gain_rows,
        "n20_worker_run_count": len(rows),
        "lambda_wall": lambda_wall,
    }


def plot_z_signal_ablation(path: Path, out_dir: Path) -> None:
    if not path.exists():
        return
    payload = load_json(path)
    results = payload.get("feature_sets") or {}
    names = ["budget_only", "probe_only", "probe_plus_budget", "leaky_current"]
    labels = ["budget", "probe", "probe+budget", "leaky current"]
    vals = [float((results.get(name) or {}).get("macro_accuracy", math.nan)) for name in names]
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    bars = ax.bar(range(len(names)), vals, color=["#999999", "#4c78a8", "#72b7b2", "#f58518"])
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("leave-one-out macro accuracy")
    ax.set_title(f"Z-signal mode prediction ablation (n={payload.get('record_count', 'unknown')})")
    for bar, value in zip(bars, vals):
        if math.isfinite(value):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.2f}", ha="center", fontsize=8)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_dir / "diag_z_signal_ablation.png", dpi=220, bbox_inches="tight")
    fig.savefig(out_dir / "diag_z_signal_ablation.pdf", bbox_inches="tight")
    plt.close(fig)


def write_readme(out_dir: Path, accounting_dir: Path, rows: list[dict[str, Any]], router: dict[str, Any], z_path: Path) -> None:
    counts = Counter((row["mode"], row["worker"]) for row in rows)
    cell_lines = [
        f"- `{mode}/{worker}`: {counts[(mode, worker)]} runs"
        for mode in analysis.MODES
        for worker in analysis.WORKERS
    ]
    router_note = (
        f"Router negative-control plots reuse processed router decisions from `{router.get('router_path')}` "
        "and recompute mode-worker losses from the n=20 confirmation frontier."
        if router.get("available")
        else "Router negative-control plots were not regenerated because processed router decisions were unavailable."
    )
    text = "\n".join(
        [
            "# n=20 confirmation appendix figures",
            "",
            "These figures were regenerated from the official confirmation/holdout raw runs only.",
            "The missing 90 pilot runs are excluded.",
            "",
            f"Worker run count: `{len(rows)}` total = 20 runs per mode-worker cell.",
            "",
            *cell_lines,
            "",
            router_note,
            "",
            f"`diag_z_signal_ablation` is regenerated from `{z_path}`. That diagnostic uses its available aggregate input, not the 180 worker-run panel.",
            "",
            f"Accounting outputs: `{accounting_dir}`.",
            "",
        ]
    )
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def save_summary(accounting_dir: Path, payload: dict[str, Any]) -> None:
    accounting_dir.mkdir(parents=True, exist_ok=True)
    (accounting_dir / "appendix_n20_confirmation_analysis.json").write_text(
        json.dumps(analysis.clean_json(payload), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def remove_non_appendix_byproducts(out_dir: Path) -> None:
    for path in out_dir.glob("*.png"):
        if path.stem not in APPENDIX_FIGURE_STEMS:
            path.unlink()
    for path in out_dir.glob("*.pdf"):
        if path.stem not in APPENDIX_FIGURE_STEMS:
            path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-root", type=Path, default=DEFAULT_EXPERIMENT_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--accounting-dir", type=Path, default=DEFAULT_ACCOUNTING_DIR)
    parser.add_argument("--router-analysis", type=Path, default=DEFAULT_ROUTER_ANALYSIS)
    parser.add_argument("--z-ablation", type=Path, default=DEFAULT_Z_ABLATION)
    parser.add_argument("--lambda-wall", type=float, default=1.0 / 1800.0)
    args = parser.parse_args()

    rows, selection = load_confirmation_rows(args.experiment_root)
    if len(rows) != 180:
        raise RuntimeError(f"Expected 180 official confirmation runs, found {len(rows)}")

    losses = {row["run_id"]: analysis.deployment_loss(row, args.lambda_wall) for row in rows}
    frontier = analysis.summarize_frontier(rows, losses, args.lambda_wall)
    router = rebuild_router_from_processed(args.router_analysis, frontier, rows, args.lambda_wall)
    threshold_report = analysis.threshold_analysis(rows, args.lambda_wall)
    router_threshold = analysis.router_threshold_analysis(router, rows, args.lambda_wall) if router.get("available") else []

    args.out_dir.mkdir(parents=True, exist_ok=True)
    certified.style()
    kappa = certified.mode_worker_kappa(rows)
    certified.plot_quality_resource_scatter(analysis, rows, kappa, args.out_dir)
    certified.plot_first_hit_ecdf(analysis, rows, kappa, args.out_dir)
    certified.plot_deployment_mix_sensitivity(analysis, rows, kappa, args.out_dir)

    analysis.plot_frontier(frontier, [args.out_dir])
    analysis.plot_threshold(rows, [args.out_dir])
    analysis.plot_router(router, [args.out_dir])
    analysis.plot_improvement_distribution(rows, [args.out_dir])
    analysis.plot_tau_distribution(rows, [args.out_dir], args.lambda_wall)
    analysis.plot_trajectories(rows, [args.out_dir])
    analysis.plot_cost_quality(rows, [args.out_dir])
    analysis.plot_cost_to_tau(rows, [args.out_dir], args.lambda_wall)
    plot_z_signal_ablation(args.z_ablation, args.out_dir)
    remove_non_appendix_byproducts(args.out_dir)

    report = {
        "analysis_label": "n20_confirmation_only",
        "worker_run_count": len(rows),
        "threshold": analysis.THRESHOLD,
        "threshold_grid": analysis.THRESHOLD_GRID,
        "lambda_wall": args.lambda_wall,
        "selection": selection,
        "frontier": frontier,
        "threshold_analysis": threshold_report,
        "router": router,
        "router_threshold_analysis": router_threshold,
        "z_signal_ablation": str(args.z_ablation),
    }
    save_summary(args.accounting_dir, report)
    analysis.write_outputs(args.accounting_dir, frontier, threshold_report, router, router_threshold)
    write_readme(args.out_dir, args.accounting_dir, rows, router, args.z_ablation)

    figures = sorted(path.name for path in args.out_dir.glob("*.png"))
    print(
        json.dumps(
            {
                "output_dir": str(args.out_dir),
                "accounting_dir": str(args.accounting_dir),
                "worker_run_count": len(rows),
                "png_count": len(figures),
                "figures": figures,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
