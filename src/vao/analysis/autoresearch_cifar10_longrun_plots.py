"""Generate reviewer-facing plots for AutoResearch long-run campaigns."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from vao.estimators import productive_mode_proxy, routing_regret, jsd
from vao.taxonomy import MODES


plt.style.use("seaborn-v0_8-whitegrid")

MODE_COLORS = {
    "layout": "#284b63",
    "indexing": "#3c6e71",
    "topk": "#d97706",
    "caching": "#8f2d56",
    "summaries": "#5c4d7d",
    "micro": "#6c757d",
}
MODEL_COLORS = ["#1f77b4", "#d95f02", "#2ca02c", "#9467bd", "#8c564b"]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _step_dirs(run_dir: Path) -> list[Path]:
    return sorted(path for path in (run_dir / "steps").glob("step_*") if path.is_dir())


def _stderr(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return float(np.std(values, ddof=1) / math.sqrt(len(values)))


def _ci_band(series: dict[int, list[float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    steps = np.array(sorted(series), dtype=int)
    means = np.array([float(np.mean(series[step])) for step in steps], dtype=float)
    errs = np.array([1.96 * _stderr(series[step]) for step in steps], dtype=float)
    return steps, means, errs


def _extract_run(run_dir: Path) -> dict[str, Any]:
    summary = _load_json(run_dir / "run_summary.json")
    baseline_loss = float(summary["baseline_loss"])
    best_visible = baseline_loss
    rows: list[dict[str, Any]] = []
    cumulative_branch_wall = 0.0
    cumulative_model_wall = 0.0
    cumulative_agent_cost = 0.0
    cumulative_training_cost = 0.0
    for step_dir in _step_dirs(run_dir):
        record = _load_json(step_dir / "step_record.json")
        meta_path = step_dir / "batch_raw_output_meta.json"
        meta = _load_json(meta_path) if meta_path.exists() else {}
        branches = record["branches"]
        gains = {str(branch["declared_mode"]): float(branch["gain"]) for branch in branches}
        pstar = productive_mode_proxy(gains)
        selected_branch = next(branch for branch in branches if bool(branch["selected_as_visible"]))
        selected_loss = float(selected_branch["latent_loss"])
        best_visible = min(best_visible, selected_loss)
        cumulative_branch_wall += sum(float(branch.get("elapsed_wall_seconds") or 0.0) for branch in branches)
        cumulative_training_cost += sum(float(branch.get("accounting_cost") or 0.0) for branch in branches)
        cumulative_model_wall += float(meta.get("elapsed_wall_seconds") or 0.0)
        cumulative_agent_cost += float(record.get("agent_cost_usd") or meta.get("cost_usd") or 0.0)
        rows.append(
            {
                "step": int(record["step"]),
                "selected_loss": selected_loss,
                "best_visible_so_far": best_visible,
                "selected_mode": str(record["selected_mode"]),
                "best_branch_mode": min(branches, key=lambda branch: float(branch["latent_loss"]))["declared_mode"],
                "routing_regret": routing_regret(gains, str(record["selected_mode"])),
                "routing_mismatch_jsd": jsd(record["mode_probs"], pstar),
                "alignment_hit": 1.0 if str(record["selected_mode"]) == str(min(branches, key=lambda branch: float(branch["latent_loss"]))["declared_mode"]) else 0.0,
                "positive_branch_count": sum(1 for branch in branches if float(branch["gain"]) > 0.0),
                "cumulative_branch_wall_seconds": cumulative_branch_wall,
                "cumulative_model_wall_seconds": cumulative_model_wall,
                "cumulative_total_wall_seconds": cumulative_branch_wall + cumulative_model_wall,
                "cumulative_training_cost": cumulative_training_cost,
                "cumulative_agent_cost_usd": cumulative_agent_cost,
                "mode_probs": {mode: float(record["mode_probs"].get(mode, 0.0)) for mode in MODES},
            }
        )
    return {
        "run_dir": str(run_dir),
        "run_name": run_dir.name,
        "model_alias": run_dir.name.split("_seed", 1)[-1].split("_", 1)[-1],
        "latent_mode": run_dir.name.split("_holdout_", 1)[1].rsplit("_seed", 1)[0] if "_holdout_" in run_dir.name else "unknown",
        "baseline_loss": baseline_loss,
        "rows": rows,
    }


def _collect(root: Path) -> list[dict[str, Any]]:
    runs = []
    for run_dir in sorted(root.iterdir()):
        if not run_dir.is_dir():
            continue
        if not (run_dir / "run_summary.json").exists():
            continue
        runs.append(_extract_run(run_dir))
    return runs


def _group_by_model(runs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[str(run["model_alias"])].append(run)
    return grouped


def _plot_action_mode_distribution(grouped: dict[str, list[dict[str, Any]]], out_dir: Path) -> None:
    fig, axes = plt.subplots(len(grouped), 1, figsize=(12, 3.8 * max(len(grouped), 1)), sharex=True)
    if not isinstance(axes, np.ndarray):
        axes = np.array([axes])
    for ax, (model, runs) in zip(axes, grouped.items(), strict=False):
        by_step = {mode: defaultdict(list) for mode in MODES}
        for run in runs:
            for row in run["rows"]:
                for mode in MODES:
                    by_step[mode][int(row["step"])].append(float(row["mode_probs"][mode]))
        steps = sorted({step for mode in MODES for step in by_step[mode]})
        stacks = []
        for mode in MODES:
            stacks.append([float(np.mean(by_step[mode][step])) for step in steps])
        ax.stackplot(steps, stacks, labels=MODES, colors=[MODE_COLORS[mode] for mode in MODES], alpha=0.92)
        ax.set_title(model)
        ax.set_ylabel("Mean q(mode)")
        ax.set_ylim(0.0, 1.0)
    axes[-1].set_xlabel("Optimization step")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=6, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_dir / "action_mode_distribution.png", dpi=220)
    plt.close(fig)


def _plot_metric_lines(grouped: dict[str, list[dict[str, Any]]], out_dir: Path, metric: str, ylabel: str, filename: str) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    for color, (model, runs) in zip(MODEL_COLORS, grouped.items(), strict=False):
        series: dict[int, list[float]] = defaultdict(list)
        for run in runs:
            for row in run["rows"]:
                series[int(row["step"])].append(float(row[metric]))
        steps, means, errs = _ci_band(series)
        ax.plot(steps, means, color=color, linewidth=2.4, label=model)
        ax.fill_between(steps, means - errs, means + errs, color=color, alpha=0.16)
    ax.set_xlabel("Optimization step")
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / filename, dpi=220)
    plt.close(fig)


def _plot_action_alignment(grouped: dict[str, list[dict[str, Any]]], out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    for color, (model, runs) in zip(MODEL_COLORS, grouped.items(), strict=False):
        series: dict[int, list[float]] = defaultdict(list)
        for run in runs:
            for row in run["rows"]:
                series[int(row["step"])].append(float(row["alignment_hit"]))
        steps, means, errs = _ci_band(series)
        ax.plot(steps, means, color=color, linewidth=2.4, label=model)
        ax.fill_between(steps, np.clip(means - errs, 0.0, 1.0), np.clip(means + errs, 0.0, 1.0), color=color, alpha=0.16)
    ax.set_xlabel("Optimization step")
    ax.set_ylabel("P(selected mode = best branch)")
    ax.set_ylim(0.0, 1.0)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "action_alignment.png", dpi=220)
    plt.close(fig)


def _plot_pairwise_terms(grouped: dict[str, list[dict[str, Any]]], out_dir: Path, baseline_model: str, tau_abs: float) -> None:
    if baseline_model not in grouped:
        return
    baseline_runs = grouped[baseline_model]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    axes = axes.flatten()
    titles = [
        "Cost term",
        "Competence proxy",
        "Routing mismatch (JSD)",
        "Routing regret",
    ]
    ylabels = [
        "log(kappa_base / kappa_model)",
        "log(p_model / p_base)",
        "Mean JSD(q, q*)",
        "Mean regret",
    ]
    for axis, title, ylabel in zip(axes, titles, ylabels, strict=False):
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.set_xlabel("Optimization step")

    baseline_series_cost: dict[int, list[float]] = defaultdict(list)
    baseline_success: dict[int, list[float]] = defaultdict(list)
    baseline_mismatch: dict[int, list[float]] = defaultdict(list)
    baseline_regret: dict[int, list[float]] = defaultdict(list)
    for run in baseline_runs:
        baseline = float(run["baseline_loss"])
        for row in run["rows"]:
            step = int(row["step"])
            baseline_series_cost[step].append(float(row["cumulative_total_wall_seconds"]))
            baseline_success[step].append(1.0 if baseline - float(row["best_visible_so_far"]) >= tau_abs else 0.0)
            baseline_mismatch[step].append(float(row["routing_mismatch_jsd"]))
            baseline_regret[step].append(float(row["routing_regret"]))

    for color, (model, runs) in zip(MODEL_COLORS, grouped.items(), strict=False):
        if model == baseline_model:
            continue
        cost_term: dict[int, list[float]] = defaultdict(list)
        competence: dict[int, list[float]] = defaultdict(list)
        mismatch: dict[int, list[float]] = defaultdict(list)
        regret: dict[int, list[float]] = defaultdict(list)
        for run in runs:
            baseline = float(run["baseline_loss"])
            for row in run["rows"]:
                step = int(row["step"])
                mean_base_cost = float(np.mean(baseline_series_cost[step]))
                cost_term[step].append(math.log(max(mean_base_cost, 1e-9) / max(float(row["cumulative_total_wall_seconds"]), 1e-9)))
                mean_base_success = float(np.mean(baseline_success[step]))
                model_success = 1.0 if baseline - float(row["best_visible_so_far"]) >= tau_abs else 0.0
                competence[step].append(math.log((model_success + 1e-6) / (mean_base_success + 1e-6)))
                mismatch[step].append(float(row["routing_mismatch_jsd"]))
                regret[step].append(float(row["routing_regret"]))

        for axis, series in zip(axes, [cost_term, competence, mismatch, regret], strict=False):
            steps, means, errs = _ci_band(series)
            axis.plot(steps, means, color=color, linewidth=2.2, label=model)
            axis.fill_between(steps, means - errs, means + errs, color=color, alpha=0.16)

    for axis in axes:
        axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "theorem_diagnostics.png", dpi=220)
    plt.close(fig)


def _write_summary(runs: list[dict[str, Any]], out_dir: Path) -> None:
    payload = []
    for run in runs:
        rows = run["rows"]
        payload.append(
            {
                "run_name": run["run_name"],
                "model_alias": run["model_alias"],
                "latent_mode": run["latent_mode"],
                "steps_completed": len(rows),
                "baseline_loss": run["baseline_loss"],
                "best_visible_loss": min(float(row["best_visible_so_far"]) for row in rows) if rows else run["baseline_loss"],
                "final_selected_loss": float(rows[-1]["selected_loss"]) if rows else run["baseline_loss"],
                "final_cumulative_total_wall_seconds": float(rows[-1]["cumulative_total_wall_seconds"]) if rows else 0.0,
                "final_cumulative_agent_cost_usd": float(rows[-1]["cumulative_agent_cost_usd"]) if rows else 0.0,
            }
        )
    (out_dir / "plot_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--baseline-model", required=True)
    parser.add_argument("--tau-abs", type=float, default=0.003)
    args = parser.parse_args(argv)

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = _collect(root)
    grouped = _group_by_model(runs)
    _write_summary(runs, out_dir)
    _plot_action_mode_distribution(grouped, out_dir)
    _plot_metric_lines(grouped, out_dir, "selected_loss", "Selected loss", "selected_loss.png")
    _plot_metric_lines(grouped, out_dir, "best_visible_so_far", "Best loss so far", "best_loss_so_far.png")
    _plot_metric_lines(grouped, out_dir, "cumulative_total_wall_seconds", "Cumulative wall seconds", "cumulative_cost.png")
    _plot_action_alignment(grouped, out_dir)
    _plot_pairwise_terms(grouped, out_dir, args.baseline_model, args.tau_abs)
    print(json.dumps({"run_count": len(runs), "models": sorted(grouped), "out_dir": str(out_dir)}, indent=2))


if __name__ == "__main__":
    main()
