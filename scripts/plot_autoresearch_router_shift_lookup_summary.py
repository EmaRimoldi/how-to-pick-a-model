"""Summarize router mode-shift and lookup-calibrated choices in one figure."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODES = ["mlp_flat", "cnn_compact", "resnet_micro"]
SIGNALS = ["Z0", "Z1", "Z2"]
WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
WORKER_LABELS = {
    "gpt_5_3_codex": "C",
    "gpt_5_4": "4",
    "gpt_5_4_mini": "m",
}
WORKER_LONG_LABELS = {
    "gpt_5_3_codex": "GPT 5.3 Codex",
    "gpt_5_4": "GPT 5.4",
    "gpt_5_4_mini": "GPT 5.4 Mini",
}
WORKER_COLORS = {
    "gpt_5_3_codex": "#4C78A8",
    "gpt_5_4": "#F58518",
    "gpt_5_4_mini": "#54A24B",
}
SIGNAL_COLORS = {"Z0": "#6B7280", "Z1": "#4C78A8", "Z2": "#F58518"}
ROUTER_MARKERS = {"GPT-5.5": "o", "GPT-5.4": "^"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def load_router_rows(router_dirs: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for router_label, path in router_dirs.items():
        for child in sorted(path.glob("*.jsonl")):
            for row in read_jsonl(child):
                row["_router_label"] = router_label
                rows.append(row)
    return rows


def load_calibration(path: Path, metric: str) -> dict[tuple[str, str], float]:
    metric_key = {
        "factored_mode_wall": "factored_mode_wall_resource",
        "end_to_end_wall": "end_to_end_wall_resource",
        "factored_mode_tokens": "factored_mode_token_resource_millions",
        "end_to_end_tokens": "end_to_end_token_resource_millions",
    }[metric]
    table: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = row.get(metric_key) or ""
            table[(row["mode"], row["agent_system"])] = float(raw) if raw else float("inf")
    return table


def calibrated_choice(row: dict[str, Any], table: dict[tuple[str, str], float]) -> str:
    posterior = (row.get("router_output") or {}).get("mode_posterior") or {}
    scores = {
        worker: sum(float(posterior.get(mode, 0.0)) * table[(mode, worker)] for mode in MODES)
        for worker in WORKERS
    }
    return min(scores, key=scores.get)


def bar_counts(rows: list[dict[str, Any]], choice_key: str) -> dict[tuple[str, str], Counter[str]]:
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        router = row["_router_label"]
        signal = row["signal_level"]
        if choice_key == "direct":
            choice = (row.get("router_output") or {}).get("selected_agent_model")
        else:
            choice = row.get("_calibrated_choice")
        if choice in WORKERS:
            counts[(router, signal)][choice] += 1
    return counts


def plot(rows: list[dict[str, Any]], out_path: Path, metric_label: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig = plt.figure(figsize=(13.2, 5.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.38, 1.0, 1.0], wspace=0.34)
    ax_scatter = fig.add_subplot(gs[0, 0])
    ax_direct = fig.add_subplot(gs[0, 1])
    ax_cal = fig.add_subplot(gs[0, 2], sharey=ax_direct)

    for router_label in ["GPT-5.5", "GPT-5.4"]:
        for signal in SIGNALS:
            xs: list[float] = []
            ys: list[float] = []
            for row in rows:
                if row["_router_label"] != router_label or row["signal_level"] != signal:
                    continue
                true_mode = row["true_mode"]
                output = row.get("router_output") or {}
                posterior = output.get("mode_posterior") or {}
                allocation = output.get("mode_allocation") or {}
                xs.append(float(posterior.get(true_mode, 0.0)))
                ys.append(float(allocation.get(true_mode, 0.0)))
            ax_scatter.scatter(
                xs,
                ys,
                s=34,
                color=SIGNAL_COLORS[signal],
                marker=ROUTER_MARKERS[router_label],
                alpha=0.68,
                edgecolor="white",
                linewidth=0.45,
                label=f"{router_label} {signal}",
            )
            if xs:
                ax_scatter.scatter(
                    [float(np.mean(xs))],
                    [float(np.mean(ys))],
                    s=145,
                    color=SIGNAL_COLORS[signal],
                    marker=ROUTER_MARKERS[router_label],
                    edgecolor="#111827",
                    linewidth=0.9,
                    zorder=6,
                )

    ax_scatter.plot([0, 1], [0, 1], color="#9CA3AF", linestyle="--", linewidth=1.2)
    ax_scatter.axvline(1 / 3, color="#D1D5DB", linewidth=1.0)
    ax_scatter.axhline(1 / 3, color="#D1D5DB", linewidth=1.0)
    ax_scatter.text(0.35, 0.29, "uninformative prior", fontsize=8, color="#6B7280")
    ax_scatter.set_xlim(0.25, 1.02)
    ax_scatter.set_ylim(0.25, 1.02)
    ax_scatter.set_xlabel(r"Posterior mass on true mode, $\pi_z(S)$")
    ax_scatter.set_ylabel(r"Allocation mass on true mode, $q_z(S)$")
    ax_scatter.set_title("A. Signal moves belief and allocation", loc="left", fontweight="bold")
    ax_scatter.grid(axis="both", alpha=0.24)
    ax_scatter.spines[["top", "right"]].set_visible(False)

    # Make a compact custom legend.
    signal_handles = [
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=SIGNAL_COLORS[s], markeredgecolor="white", markersize=8, label=s)
        for s in SIGNALS
    ]
    router_handles = [
        plt.Line2D([0], [0], marker=ROUTER_MARKERS[r], color="#111827", linestyle="none", markersize=7, label=r)
        for r in ["GPT-5.5", "GPT-5.4"]
    ]
    leg1 = ax_scatter.legend(handles=signal_handles, title="Signal", loc="lower right", frameon=True, fontsize=8, title_fontsize=8)
    ax_scatter.add_artist(leg1)
    ax_scatter.legend(handles=router_handles, title="Router", loc="center right", frameon=True, fontsize=8, title_fontsize=8)

    def draw_choice_bars(ax: plt.Axes, choice_key: str, title: str) -> None:
        counts = bar_counts(rows, choice_key)
        positions: list[float] = []
        labels: list[str] = []
        x = 0.0
        for router_label in ["GPT-5.5", "GPT-5.4"]:
            for signal in SIGNALS:
                total = sum(counts[(router_label, signal)].values())
                bottom = 0.0
                for worker in WORKERS:
                    value = counts[(router_label, signal)][worker] / total if total else 0.0
                    ax.bar(
                        x,
                        value,
                        bottom=bottom,
                        width=0.72,
                        color=WORKER_COLORS[worker],
                        edgecolor="white",
                        linewidth=0.8,
                    )
                    if value > 0.12:
                        ax.text(
                            x,
                            bottom + value / 2,
                            str(counts[(router_label, signal)][worker]),
                            ha="center",
                            va="center",
                            fontsize=8,
                            color="white",
                            fontweight="bold",
                        )
                    bottom += value
                positions.append(x)
                labels.append(signal)
                x += 1.0
            x += 0.62
        ax.set_xticks(positions)
        ax.set_xticklabels(labels)
        ax.set_ylim(0, 1.0)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.grid(axis="y", alpha=0.24)
        ax.grid(axis="x", visible=False)
        ax.spines[["top", "right"]].set_visible(False)
        ax.axvline(2.81, color="#D1D5DB", linewidth=1.0)
        for idx, router_label in enumerate(["GPT-5.5", "GPT-5.4"]):
            center = idx * (len(SIGNALS) + 0.62) + 1.0
            ax.text(center, -0.16, router_label, ha="center", va="top", fontsize=8.5, transform=ax.get_xaxis_transform())

    draw_choice_bars(ax_direct, "direct", "B. Direct router choice")
    draw_choice_bars(ax_cal, "calibrated", "C. Lookup-calibrated choice")
    ax_direct.set_ylabel("Share of instances")
    plt.setp(ax_cal.get_yticklabels(), visible=False)

    worker_handles = [
        plt.Rectangle((0, 0), 1, 1, color=WORKER_COLORS[worker], label=f"{WORKER_LABELS[worker]} = {WORKER_LONG_LABELS[worker]}")
        for worker in WORKERS
    ]
    fig.legend(handles=worker_handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.66, 0.045), fontsize=8)
    fig.suptitle("Mode recognition shifts cleanly; lookup stabilizes worker choice", fontsize=14, fontweight="bold", y=0.985)
    fig.subplots_adjust(left=0.06, right=0.995, bottom=0.27, top=0.88, wspace=0.34)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=250, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt55-dir", required=True)
    parser.add_argument("--gpt54-dir", required=True)
    parser.add_argument("--calibration-table", required=True)
    parser.add_argument("--calibration-metric", default="factored_mode_wall", choices=["factored_mode_wall", "end_to_end_wall", "factored_mode_tokens", "end_to_end_tokens"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--paper-figure-dir", default=None)
    args = parser.parse_args()

    rows = load_router_rows({"GPT-5.5": Path(args.gpt55_dir), "GPT-5.4": Path(args.gpt54_dir)})
    table = load_calibration(Path(args.calibration_table), args.calibration_metric)
    for row in rows:
        row["_calibrated_choice"] = calibrated_choice(row, table)

    out_path = Path(args.output)
    metric_label = args.calibration_metric.replace("_", " ")
    plot(rows, out_path, metric_label)

    copied: list[str] = []
    if args.paper_figure_dir:
        paper_dir = Path(args.paper_figure_dir)
        paper_dir.mkdir(parents=True, exist_ok=True)
        for path in [out_path, out_path.with_suffix(".pdf")]:
            target = paper_dir / path.name
            shutil.copy2(path, target)
            copied.append(str(target))
    print(json.dumps({"rows": len(rows), "figure": str(out_path), "copied": copied}, indent=2))


if __name__ == "__main__":
    main()
