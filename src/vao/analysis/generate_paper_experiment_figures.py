"""Generate current paper figures for the AutoResearch experimental section."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path("/home/erimoldi/openclaw_remote/projects/NeurIPS_2026")
ARTIFACTS = PROJECT_ROOT / "artifacts" / "autoresearch_cifar10"
PAPER_FIG_DIR = PROJECT_ROOT / "paper_overleaf" / "figures" / "autoresearch"
PAPER_FIG_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ORDER = ["gpt_5_4_mini", "gpt_5_3_codex", "gpt_5_3_codex_spark", "claude_sonnet"]
MODEL_LABELS = ["GPT-5.4 mini", "GPT-5.3 Codex", "GPT-5.3 Codex Spark", "Claude Sonnet"]
MODE_ORDER = [
    "lr-sensitive",
    "regularization-sensitive",
    "optimizer-sensitive",
    "data-skew-sensitive",
    "capacity-sensitive",
    "schedule-sensitive",
]
MODE_LABELS = [
    "LR",
    "Reg.",
    "Opt.",
    "Skew",
    "Cap.",
    "Sched.",
]

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.titlesize": 12,
})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def savefig(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(PAPER_FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(PAPER_FIG_DIR / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_heatmap(ax: plt.Axes, data: np.ndarray, *, vmin: float, vmax: float, cmap: str, title: str, annotate: list[list[str]] | None = None) -> None:
    im = ax.imshow(data, vmin=vmin, vmax=vmax, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(MODE_LABELS)))
    ax.set_xticklabels(MODE_LABELS, rotation=30, ha="right")
    ax.set_yticks(range(len(MODEL_LABELS)))
    ax.set_yticklabels(MODEL_LABELS)
    ax.set_title(title)
    if annotate is not None:
        for i in range(len(MODEL_ORDER)):
            for j in range(len(MODE_ORDER)):
                text = annotate[i][j]
                if text:
                    ax.text(j, i, text, ha="center", va="center", fontsize=8, color="black")
    return im


def build_current_overview() -> None:
    early = load_json(ARTIFACTS / "threshold_calibration_sweep.json")
    nostop = load_json(ARTIFACTS / "threshold_calibration_sweep_nostop_partial.json")
    z_multi = load_json(ARTIFACTS / "z_signal_ablation_multiseed.json")

    early_map = {(row["model_alias"], row["task_mode_true"]): row for row in early["by_model_mode"] if abs(row["threshold"] - 0.05) < 1e-12}
    nostop_map = {(row["model_alias"], row["task_mode_true"]): row for row in nostop["by_model_mode"] if abs(row["threshold"] - 0.05) < 1e-12}

    entry = np.full((len(MODEL_ORDER), len(MODE_ORDER)), np.nan)
    entry_ann = [["" for _ in MODE_ORDER] for _ in MODEL_ORDER]
    occ = np.full((len(MODEL_ORDER), len(MODE_ORDER)), np.nan)
    occ_ann = [["" for _ in MODE_ORDER] for _ in MODEL_ORDER]
    for i, model in enumerate(MODEL_ORDER):
        for j, mode in enumerate(MODE_ORDER):
            row = early_map.get((model, mode))
            if row is not None:
                entry[i, j] = float(row.get("entry_success_prob", row.get("success_prob", 0.0)))
                tau = row.get("mean_tau")
                entry_ann[i][j] = f"{entry[i,j]:.0f}" if tau is None else f"{entry[i,j]:.0f}\n$\\tau$={tau:g}"
            row = nostop_map.get((model, mode))
            if row is not None:
                occ[i, j] = float(row.get("mean_selected_threshold_occupancy", row.get("mean_selected_hit_rate", 0.0)))
                occ_ann[i][j] = f"{occ[i,j]:.2f}"
            else:
                occ_ann[i][j] = "pending"

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0))
    im0 = make_heatmap(axes[0, 0], entry, vmin=0.0, vmax=1.0, cmap="Blues", title="Entry competence at $\\delta=0.05$ (24/24 early-stop cells)", annotate=entry_ann)
    plt.colorbar(im0, ax=axes[0, 0], fraction=0.046, pad=0.04)

    masked_occ = np.ma.masked_invalid(occ)
    cmap = plt.cm.Oranges.copy()
    cmap.set_bad(color="#f2f2f2")
    im1 = axes[0, 1].imshow(masked_occ, vmin=0.0, vmax=1.0, cmap=cmap, aspect="auto")
    axes[0, 1].set_xticks(range(len(MODE_LABELS)))
    axes[0, 1].set_xticklabels(MODE_LABELS, rotation=30, ha="right")
    axes[0, 1].set_yticks(range(len(MODEL_LABELS)))
    axes[0, 1].set_yticklabels(MODEL_LABELS)
    axes[0, 1].set_title("Occupancy at $\\delta=0.05$ (current 20/24 no-stop snapshot)")
    for i in range(len(MODEL_ORDER)):
        for j in range(len(MODE_ORDER)):
            axes[0, 1].text(j, i, occ_ann[i][j], ha="center", va="center", fontsize=8)
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

    overall = sorted(early["overall"], key=lambda row: row["threshold"])
    thresholds = [row["threshold"] for row in overall]
    entry_prob = [row["success_prob"] for row in overall]
    mean_tau = [row["mean_tau"] for row in overall]
    axes[1, 0].plot(thresholds, entry_prob, marker="o", linewidth=2.2, label="entry success probability")
    ax_tau = axes[1, 0].twinx()
    ax_tau.plot(thresholds, mean_tau, marker="s", linestyle="--", color="#444444", linewidth=1.8, label="mean $\\tau$")
    axes[1, 0].axvline(0.05, color="#cc0000", linestyle=":", linewidth=1.5)
    axes[1, 0].set_xlabel("relative improvement threshold $\\delta$")
    axes[1, 0].set_ylabel("entry success probability")
    ax_tau.set_ylabel("mean first-passage step")
    axes[1, 0].set_title("Threshold calibration from the 24-cell early-stop pilot")
    lines1, labels1 = axes[1, 0].get_legend_handles_labels()
    lines2, labels2 = ax_tau.get_legend_handles_labels()
    axes[1, 0].legend(lines1 + lines2, labels1 + labels2, loc="lower left")

    feature_names = ["budget_only", "probe_only", "probe_plus_budget", "leaky_current"]
    xs = np.arange(len(feature_names))
    heights = [z_multi["feature_sets"][name]["macro_accuracy"] for name in feature_names]
    bars = axes[1, 1].bar(xs, heights, color=["#999999", "#2a6fdb", "#5aa0ff", "#e38d2c"])
    axes[1, 1].set_xticks(xs)
    axes[1, 1].set_xticklabels(["budget only", "probe only", "probe + budget", "leaky current"], rotation=25, ha="right")
    axes[1, 1].set_ylim(0.0, 1.0)
    axes[1, 1].set_ylabel("leave-one-out macro accuracy")
    axes[1, 1].set_title("Mode-prediction signal ablation on 30 baseline-only probes")
    for bar, value in zip(bars, heights):
        axes[1, 1].text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Current AutoResearch protocol-freezing overview", y=1.02)
    savefig(fig, "current_protocol_overview")


def build_throughput_figure() -> None:
    short = load_json(ARTIFACTS / "throughput" / "throughput_report.json")
    long = load_json(ARTIFACTS / "throughput_long" / "throughput_report.json")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    colors = plt.cm.tab10(np.linspace(0, 1, len(MODE_ORDER)))
    short_rows = short["summary"]
    for mode, color in zip(MODE_ORDER, colors):
        rows = sorted([r for r in short_rows if r["mode"] == mode], key=lambda r: r["max_train_steps"])
        if not rows:
            continue
        axes[0].plot([r["max_train_steps"] for r in rows], [r["median_val_loss"] for r in rows], marker="o", linewidth=1.6, color=color, label=mode)
    axes[0].set_xscale("log", base=2)
    axes[0].set_xlabel("inner training steps")
    axes[0].set_ylabel("median validation loss")
    axes[0].set_title("Short-budget verifier response (2--128 steps)")
    axes[0].legend(fontsize=7, ncol=2)

    long_rows = long["summary"]
    for mode, color in zip(["lr-sensitive", "regularization-sensitive", "schedule-sensitive"], colors[:3]):
        rows = sorted([r for r in long_rows if r["mode"] == mode], key=lambda r: r["max_train_steps"])
        axes[1].plot([r["max_train_steps"] for r in rows], [r["median_training_seconds"] for r in rows], marker="o", linewidth=2.0, color=color, label=mode)
    axes[1].set_xscale("log", base=2)
    axes[1].set_xlabel("inner training steps")
    axes[1].set_ylabel("median training seconds")
    axes[1].set_title("Long-budget verifier cost (64--512 steps)")
    axes[1].legend(fontsize=8)
    savefig(fig, "throughput_calibration")


def build_init_figure() -> None:
    data = load_json(ARTIFACTS / "init_diagnostics" / "init_diagnostics_report.json")
    modes = MODE_ORDER
    scores = []
    target_gains = []
    labels = []
    for mode in modes:
        row = data[mode]
        scores.append(float(row["recommended_score"]))
        candidate = row["recommended_candidate"]
        cand = row["candidates"][candidate]
        target_gains.append(float(cand["target_gain"]))
        labels.append(candidate)
    x = np.arange(len(modes))
    width = 0.36
    fig, ax = plt.subplots(figsize=(11.2, 4.2))
    ax.axhline(0.0, color="#444444", linewidth=1.0)
    b1 = ax.bar(x - width/2, scores, width, label="recommended score (margin over controls)", color="#2a6fdb")
    b2 = ax.bar(x + width/2, target_gains, width, label="target gain over baseline", color="#e38d2c")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{label}\n({cand})" for label, cand in zip(MODE_LABELS, labels)])
    ax.set_ylabel("validation-loss improvement")
    ax.set_title("Initialization diagnostics used to freeze mode-specific starting states")
    ax.legend(loc="upper left")
    for bars in [b1, b2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + (0.00035 if h >= 0 else -0.0008), f"{h:.3f}", ha="center", va="bottom" if h >= 0 else "top", fontsize=7)
    savefig(fig, "init_diagnostics")


def build_threshold_mode_figure() -> None:
    data = load_json(ARTIFACTS / "threshold_calibration_sweep.json")
    thresholds = data["thresholds"]
    mode_map = {(row["task_mode_true"], row["threshold"]): row for row in data["by_mode"]}
    matrix = np.zeros((len(MODE_ORDER), len(thresholds)))
    for i, mode in enumerate(MODE_ORDER):
        for j, threshold in enumerate(thresholds):
            row = mode_map[(mode, threshold)]
            matrix[i, j] = float(row.get("entry_success_prob", row["success_prob"]))
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    im = ax.imshow(matrix, vmin=0.0, vmax=1.0, cmap="Purples", aspect="auto")
    ax.set_xticks(range(len(thresholds)))
    ax.set_xticklabels([f"{t:.2f}" for t in thresholds])
    ax.set_yticks(range(len(MODE_LABELS)))
    ax.set_yticklabels(MODE_LABELS)
    ax.set_xlabel("relative improvement threshold $\\delta$")
    ax.set_title("Early-stop entry success by mode and threshold")
    for i in range(len(MODE_ORDER)):
        for j in range(len(thresholds)):
            ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center", fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    savefig(fig, "threshold_by_mode")


def build_cost_figure() -> None:
    run_root = PROJECT_ROOT / "runs" / "autoresearch_cifar10" / "threshold_calibration_pilot"
    values: dict[str, list[float]] = {model: [] for model in MODEL_ORDER}
    for summary_path in run_root.glob("*/run_summary.json"):
        model = summary_path.parent.name.split("_seed")[1].split("_", 1)[1]
        values[model].append(float(load_json(summary_path)["elapsed_wall_seconds"]))
    means = [sum(values[m]) / len(values[m]) for m in MODEL_ORDER]
    medians = []
    for model in MODEL_ORDER:
        xs = sorted(values[model])
        medians.append(xs[len(xs)//2] if len(xs) % 2 == 1 else 0.5 * (xs[len(xs)//2 - 1] + xs[len(xs)//2]))
    x = np.arange(len(MODEL_ORDER))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    b1 = ax.bar(x - width/2, means, width, color="#2a6fdb", label="mean wall time")
    b2 = ax.bar(x + width/2, medians, width, color="#e38d2c", label="median wall time")
    ax.set_xticks(x)
    ax.set_xticklabels(MODEL_LABELS, rotation=20, ha="right")
    ax.set_ylabel("seconds per trajectory")
    ax.set_title("Early-stop pilot wall-clock cost by model (24 trajectories)")
    ax.legend()
    for bars in [b1, b2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 4, f"{bar.get_height():.0f}", ha="center", va="bottom", fontsize=8)
    savefig(fig, "pilot_costs")


def build_z_ablation_figure() -> None:
    single = load_json(ARTIFACTS / "z_signal_ablation_single_seed.json")
    multi = load_json(ARTIFACTS / "z_signal_ablation_multiseed.json")
    names = ["budget_only", "probe_only", "probe_plus_budget", "leaky_current"]
    labels = ["budget only", "probe only", "probe + budget", "leaky current"]
    x = np.arange(len(names))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.8, 4.2))
    b1 = ax.bar(x - width/2, [single["feature_sets"][name]["macro_accuracy"] for name in names], width, color="#84b6f4", label="single-seed (24 runs)")
    b2 = ax.bar(x + width/2, [multi["feature_sets"][name]["macro_accuracy"] for name in names], width, color="#2a6fdb", label="multi-seed (30 runs)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("leave-one-out macro accuracy")
    ax.set_title("Restricted-$Z$ ablation for start-of-run mode prediction")
    ax.legend()
    for bars in [b1, b2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=8)
    savefig(fig, "z_ablation")


def build_nostop_snapshot_figure() -> None:
    nostop = load_json(ARTIFACTS / "threshold_calibration_sweep_nostop_partial.json")
    rows = [r for r in nostop["by_model_mode"] if abs(r["threshold"] - 0.05) < 1e-12]
    entry_map = {(row["model_alias"], row["task_mode_true"]): float(row.get("entry_success_prob", row["success_prob"])) for row in rows}
    occ_map = {(row["model_alias"], row["task_mode_true"]): float(row.get("mean_selected_threshold_occupancy", row.get("mean_selected_hit_rate", 0.0))) for row in rows}
    entry = np.full((len(MODEL_ORDER), len(MODE_ORDER)), np.nan)
    occ = np.full((len(MODEL_ORDER), len(MODE_ORDER)), np.nan)
    entry_ann = [["" for _ in MODE_ORDER] for _ in MODEL_ORDER]
    occ_ann = [["" for _ in MODE_ORDER] for _ in MODEL_ORDER]
    for i, model in enumerate(MODEL_ORDER):
        for j, mode in enumerate(MODE_ORDER):
            if (model, mode) in entry_map:
                entry[i, j] = entry_map[(model, mode)]
                entry_ann[i][j] = f"{entry[i,j]:.0f}"
                occ[i, j] = occ_map[(model, mode)]
                occ_ann[i][j] = f"{occ[i,j]:.2f}"
            else:
                entry_ann[i][j] = "pending"
                occ_ann[i][j] = "pending"
    fig, axes = plt.subplots(1, 2, figsize=(11.3, 4.5))
    im0 = make_heatmap(axes[0], np.ma.masked_invalid(entry), vmin=0.0, vmax=1.0, cmap="Blues", title="Entry success (20/24 no-stop cells)", annotate=entry_ann)
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    im1 = make_heatmap(axes[1], np.ma.masked_invalid(occ), vmin=0.0, vmax=1.0, cmap="Oranges", title="Threshold occupancy (same partial snapshot)", annotate=occ_ann)
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    savefig(fig, "nostop_partial_snapshot")


def main() -> None:
    build_current_overview()
    build_throughput_figure()
    build_init_figure()
    build_threshold_mode_figure()
    build_cost_figure()
    build_z_ablation_figure()
    build_nostop_snapshot_figure()
    print(json.dumps({"output_dir": str(PAPER_FIG_DIR)}, indent=2))


if __name__ == "__main__":
    main()
