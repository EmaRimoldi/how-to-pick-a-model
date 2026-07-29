"""Publication-style multi-model visuals for oracle-family experiments."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from vao.analysis.task_mode_decomposition import _filter_complete_models, load_attempt_records, summarize_attempts, summarize_models
from vao.analysis.task_mode_robustness import wilson_interval


def build_visuals(
    roots: list[Path],
    *,
    out_dir: Path,
    success_threshold: float,
    success_mode: str,
    improvement_threshold: float,
    pilot_split: str,
    holdout_split: str,
) -> dict[str, str]:
    attempts = load_attempt_records(
        roots,
        success_threshold=success_threshold,
        success_mode=success_mode,
        improvement_threshold=improvement_threshold,
    )
    summary = summarize_attempts(attempts, cost_metric="wall_seconds")
    summary = _filter_complete_models(summary, pilot_split=pilot_split, holdout_split=holdout_split)
    priors = {str(item): 1.0 / len(summary[summary["split"] == holdout_split]["task_mode_true"].unique()) for item in summary[summary["split"] == holdout_split]["task_mode_true"].unique()}
    holdout_models = summarize_models(summary, split=holdout_split, task_priors=priors)
    pilot_models = summarize_models(summary, split=pilot_split, task_priors=priors)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "holdout_success_heatmap": str(out_dir / "holdout_success_heatmap.png"),
        "holdout_cost_heatmap": str(out_dir / "holdout_cost_heatmap.png"),
        "holdout_improvement_heatmap": str(out_dir / "holdout_improvement_heatmap.png"),
        "holdout_pareto": str(out_dir / "holdout_pareto.png"),
        "objective_bars": str(out_dir / "pilot_holdout_objectives.png"),
        "pairwise_mode_wins": str(out_dir / "pairwise_mode_wins.png"),
    }
    _plot_heatmap(summary, split=holdout_split, value_column="success_prob", path=Path(outputs["holdout_success_heatmap"]), title="Holdout success probability", annotate_trials=True)
    _plot_heatmap(summary, split=holdout_split, value_column="median_cost", path=Path(outputs["holdout_cost_heatmap"]), title="Holdout median wall-clock cost (s)", value_format="{:.1f}")
    _plot_heatmap(summary, split=holdout_split, value_column="mean_relative_improvement", path=Path(outputs["holdout_improvement_heatmap"]), title="Holdout mean relative improvement", value_format="{:.2f}")
    _plot_pareto(summary, attempts, split=holdout_split, path=Path(outputs["holdout_pareto"]))
    _plot_objectives(pilot_models, holdout_models, path=Path(outputs["objective_bars"]))
    _plot_pairwise_mode_wins(summary, split=holdout_split, path=Path(outputs["pairwise_mode_wins"]))
    _write_report(outputs, out_dir / "report.md")
    return outputs


def _label(model_id: str) -> str:
    return (
        model_id.replace("gpt-5.3-", "")
        .replace("gpt-5.4-", "5.4-")
        .replace("claude_", "")
        .replace("-batch-strict", "")
        .replace("-mini", "-mini")
    )


def _plot_heatmap(
    summary: pd.DataFrame,
    *,
    split: str,
    value_column: str,
    path: Path,
    title: str,
    annotate_trials: bool = False,
    value_format: str = "{:.2f}",
) -> None:
    frame = summary[summary["split"] == split].copy()
    pivot = frame.pivot(index="task_mode_true", columns="model_id", values=value_column)
    pivot = pivot[sorted(pivot.columns)]
    fig, ax = plt.subplots(figsize=(1.8 * len(pivot.columns) + 2.5, 3.6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([_label(col) for col in pivot.columns], rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(list(pivot.index))
    ax.set_title(title)
    for i, task_mode in enumerate(pivot.index):
        for j, model_id in enumerate(pivot.columns):
            value = pivot.iloc[i, j]
            text = value_format.format(value)
            if annotate_trials:
                trials = int(
                    frame[(frame["task_mode_true"] == task_mode) & (frame["model_id"] == model_id)]["attempt_count"].iloc[0]
                )
                text += f"\n(n={trials})"
            ax.text(j, i, text, ha="center", va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_pareto(summary: pd.DataFrame, attempts: list[Any], *, split: str, path: Path) -> None:
    frame = summary[summary["split"] == split].copy()
    task_modes = sorted(frame["task_mode_true"].unique())
    fig, axes = plt.subplots(1, len(task_modes), figsize=(5.5 * len(task_modes), 4.6), squeeze=False)
    attempts_by_key: dict[tuple[str, str, str], list[Any]] = {}
    for attempt in attempts:
        attempts_by_key.setdefault((attempt.split, attempt.task_mode_true, attempt.model_id), []).append(attempt)
    colors = plt.cm.tab10.colors
    for ax, task_mode in zip(axes[0], task_modes):
        rows = frame[frame["task_mode_true"] == task_mode].sort_values("median_cost")
        for idx, (_, row) in enumerate(rows.iterrows()):
            key = (split, task_mode, str(row["model_id"]))
            items = attempts_by_key[key]
            successes = sum(1 for item in items if item.success)
            trials = len(items)
            lo, hi = wilson_interval(successes, trials)
            x = float(row["median_cost"])
            y = float(row["success_prob"])
            lower = max(0.0, y - lo)
            upper = max(0.0, hi - y)
            ax.errorbar(x, y, yerr=[[lower], [upper]], fmt="o", color=colors[idx % len(colors)], capsize=3)
            ax.annotate(_label(str(row["model_id"])), (x, y), textcoords="offset points", xytext=(4, 6), fontsize=8)
        ax.set_xscale("log")
        ax.set_xlabel("Median wall-clock cost (s, log)")
        ax.set_ylabel("Success probability")
        ax.set_title(task_mode)
        ax.grid(alpha=0.25)
    fig.suptitle("Holdout Pareto frontier by task mode", fontsize=15)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_objectives(pilot_models: pd.DataFrame, holdout_models: pd.DataFrame, *, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, frame, title in [
        (axes[0], pilot_models, "Pilot expected cost-adjusted objective"),
        (axes[1], holdout_models, "Holdout expected cost-adjusted objective"),
    ]:
        ordered = frame.sort_values("expected_cost_adjusted_nll")
        ax.barh([_label(str(item)) for item in ordered["model_id"]], ordered["expected_cost_adjusted_nll"], color="#2563eb")
        ax.set_title(title)
        ax.set_xlabel("Expected cost-adjusted NLL")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _plot_pairwise_mode_wins(summary: pd.DataFrame, *, split: str, path: Path) -> None:
    frame = summary[summary["split"] == split].copy()
    models = sorted(frame["model_id"].unique())
    task_modes = sorted(frame["task_mode_true"].unique())
    lookup = {
        (str(row["task_mode_true"]), str(row["model_id"])): row
        for _, row in frame.iterrows()
    }
    matrix = []
    for left in models:
        row_values = []
        for right in models:
            wins = 0
            for task_mode in task_modes:
                left_row = lookup[(task_mode, left)]
                right_row = lookup[(task_mode, right)]
                left_score = -math.log(max(float(left_row["success_prob"]), 1e-6)) + math.log(max(float(left_row["median_cost"]), 1e-6))
                right_score = -math.log(max(float(right_row["success_prob"]), 1e-6)) + math.log(max(float(right_row["median_cost"]), 1e-6))
                if left_score < right_score:
                    wins += 1
            row_values.append(wins)
        matrix.append(row_values)
    fig, ax = plt.subplots(figsize=(1.6 * len(models) + 2.5, 1.2 * len(models) + 2.0))
    im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=len(task_modes))
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels([_label(item) for item in models], rotation=25, ha="right")
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels([_label(item) for item in models])
    ax.set_title("Pairwise mode wins (holdout)")
    for i in range(len(models)):
        for j in range(len(models)):
            ax.text(j, i, str(matrix[i][j]), ha="center", va="center", color="black", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def _write_report(outputs: dict[str, str], path: Path) -> None:
    lines = [
        "# Oracle-Family Multi-Model Visuals",
        "",
        "## Figures",
        "",
    ]
    for label, artifact in outputs.items():
        lines.append(f"- {label}: `{artifact}`")
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
    args = parser.parse_args(argv)
    outputs = build_visuals(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        success_threshold=args.success_threshold,
        success_mode=args.success_mode,
        improvement_threshold=args.improvement_threshold,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
    )
    print(outputs)


if __name__ == "__main__":
    main()
