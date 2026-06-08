"""Plot mode-posterior and allocation shifts for allocation-router outputs."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODES = ["mlp_flat", "cnn_compact", "resnet_micro"]
MODE_LABELS = {"mlp_flat": "MLP", "cnn_compact": "CNN", "resnet_micro": "ResNet"}
MODE_COLORS = {"mlp_flat": "#4C78A8", "cnn_compact": "#54A24B", "resnet_micro": "#E45756"}
SIGNALS = ["Z0", "Z1", "Z2"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.glob("**/*.jsonl")):
                rows.extend(read_jsonl(child))
        else:
            rows.extend(read_jsonl(path))
    return rows


def mean_weights(rows: list[dict[str, Any]], field: str) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        true_mode = str(row.get("true_mode") or "")
        signal = str(row.get("signal_level") or "")
        weights = (row.get("router_output") or {}).get(field) or {}
        if true_mode in MODES and signal in SIGNALS:
            grouped[(true_mode, signal)].append({mode: float(weights.get(mode, 0.0)) for mode in MODES})
    out: dict[tuple[str, str], dict[str, float]] = {}
    for key, values in grouped.items():
        out[key] = {mode: float(np.mean([item[mode] for item in values])) for mode in MODES}
    return out


def true_mode_masses(rows: list[dict[str, Any]], field: str) -> dict[str, list[float]]:
    out = {signal: [] for signal in SIGNALS}
    for row in rows:
        signal = str(row.get("signal_level") or "")
        true_mode = str(row.get("true_mode") or "")
        weights = (row.get("router_output") or {}).get(field) or {}
        if signal in SIGNALS and true_mode in MODES:
            out[signal].append(float(weights.get(true_mode, 0.0)))
    return out


def plot_stacked_shift(rows: list[dict[str, Any]], out_path: Path, title: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(11.2, 6.1), sharey=True)
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.99)
    fields = [("mode_posterior", "Mode posterior"), ("mode_allocation", "Mode allocation")]

    for row_idx, (field, label) in enumerate(fields):
        means = mean_weights(rows, field)
        for col_idx, true_mode in enumerate(MODES):
            ax = axes[row_idx, col_idx]
            bottoms = np.zeros(len(SIGNALS))
            for mode in MODES:
                values = [means.get((true_mode, signal), {}).get(mode, math.nan) for signal in SIGNALS]
                ax.bar(
                    SIGNALS,
                    values,
                    bottom=bottoms,
                    color=MODE_COLORS[mode],
                    width=0.64,
                    edgecolor="white",
                    linewidth=0.8,
                    label=MODE_LABELS[mode],
                )
                bottoms += np.array([0.0 if math.isnan(value) else value for value in values])
            true_values = [means.get((true_mode, signal), {}).get(true_mode, math.nan) for signal in SIGNALS]
            for idx, value in enumerate(true_values):
                if math.isfinite(value):
                    ax.text(idx, min(value + 0.035, 0.97), f"{value:.2f}", ha="center", va="bottom", fontsize=8)
            ax.set_ylim(0, 1.05)
            ax.set_title(f"True mode: {MODE_LABELS[true_mode]}", fontsize=10)
            if col_idx == 0:
                ax.set_ylabel(label)
            ax.grid(axis="y", alpha=0.25)
            ax.grid(axis="x", visible=False)
            ax.spines[["top", "right"]].set_visible(False)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.text(0.5, 0.035, "Numbers above bars are mean weight on the true mode.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_true_mass_distribution(rows: list[dict[str, Any]], out_path: Path, title: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    rng = np.random.default_rng(20260529)
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    offsets = {"mode_posterior": -0.16, "mode_allocation": 0.16}
    labels = {"mode_posterior": "posterior", "mode_allocation": "allocation"}
    colors = {"mode_posterior": "#4C78A8", "mode_allocation": "#F58518"}

    for field in ["mode_posterior", "mode_allocation"]:
        masses = true_mode_masses(rows, field)
        positions = np.arange(len(SIGNALS), dtype=float) + offsets[field]
        data = [masses[signal] for signal in SIGNALS]
        bp = ax.boxplot(
            data,
            positions=positions,
            widths=0.24,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "white", "linewidth": 1.4},
            boxprops={"facecolor": colors[field], "edgecolor": "none", "alpha": 0.78},
            whiskerprops={"color": colors[field], "linewidth": 1.2},
            capprops={"color": colors[field], "linewidth": 1.2},
        )
        for pos, values in zip(positions, data):
            jitter = rng.normal(0.0, 0.025, len(values))
            ax.scatter(
                np.full(len(values), pos) + jitter,
                values,
                s=18,
                color=colors[field],
                alpha=0.42,
                edgecolor="white",
                linewidth=0.35,
            )
        bp["boxes"][0].set_label(labels[field])

    ax.set_xticks(np.arange(len(SIGNALS)))
    ax.set_xticklabels(SIGNALS)
    ax.set_ylim(-0.02, 1.04)
    ax.set_ylabel("Weight assigned to the true mode")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    ax.grid(axis="x", visible=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=240, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("router_paths", nargs="+")
    parser.add_argument("--router-label", default="GPT-5.5 router")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--paper-figure-dir", default=None)
    args = parser.parse_args()

    rows = load_rows([Path(path) for path in args.router_paths])
    out_dir = Path(args.output_dir)
    stem = args.router_label.lower().replace(" ", "_").replace("-", "").replace(".", "")
    stacked = out_dir / f"{stem}_mode_weight_shift.png"
    dist = out_dir / f"{stem}_true_mode_mass_distribution.png"
    plot_stacked_shift(rows, stacked, f"{args.router_label}: mode-weight shift across signals")
    plot_true_mass_distribution(rows, dist, f"{args.router_label}: true-mode weight distribution")

    copied: list[str] = []
    if args.paper_figure_dir:
        paper_dir = Path(args.paper_figure_dir)
        paper_dir.mkdir(parents=True, exist_ok=True)
        for path in [stacked, stacked.with_suffix(".pdf"), dist, dist.with_suffix(".pdf")]:
            target = paper_dir / path.name
            shutil.copy2(path, target)
            copied.append(str(target))

    print(json.dumps({"rows": len(rows), "figures": [str(stacked), str(dist)], "copied": copied}, indent=2))


if __name__ == "__main__":
    main()
