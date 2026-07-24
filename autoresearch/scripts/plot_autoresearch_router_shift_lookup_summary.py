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
ROUTER_MARKERS = {"GPT-5.5": "o", "GPT-5.4": "^", "GPT-5.4 Mini": "s"}


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


def router_order(rows: list[dict[str, Any]]) -> list[str]:
    preferred = ["GPT-5.5", "GPT-5.4", "GPT-5.4 Mini"]
    present = {row["_router_label"] for row in rows}
    ordered = [router for router in preferred if router in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def plot(rows: list[dict[str, Any]], out_path: Path, metric_label: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    routers = router_order(rows)
    fig_height = 5.5 if len(routers) <= 2 else 6.2
    fig = plt.figure(figsize=(13.2, fig_height))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.35], wspace=0.28)
    ax_scatter = fig.add_subplot(gs[0, 0])
    ax_choice = fig.add_subplot(gs[0, 1])

    for router_label in routers:
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
        for r in routers
    ]
    leg1 = ax_scatter.legend(handles=signal_handles, title="Signal", loc="lower right", frameon=True, fontsize=8, title_fontsize=8)
    ax_scatter.add_artist(leg1)
    ax_scatter.legend(handles=router_handles, title="Router", loc="center right", frameon=True, fontsize=8, title_fontsize=8)

    direct_counts = bar_counts(rows, "direct")
    calibrated_counts = bar_counts(rows, "calibrated")
    worker_x = {worker: idx for idx, worker in enumerate(WORKERS)}
    y_positions: dict[tuple[str, str], float] = {}
    y_labels: list[str] = []
    y = 0.0
    for router in routers:
        for signal in SIGNALS:
            y_positions[(router, signal)] = y
            y_labels.append(f"{router}  {signal}")
            y += 1.0
        y += 0.45

    max_count = max(
        [
            count
            for counts in list(direct_counts.values()) + list(calibrated_counts.values())
            for count in counts.values()
        ]
        or [1]
    )

    for idx, worker in enumerate(WORKERS):
        ax_choice.axvline(idx, color="#F3F4F6", linewidth=1.0, zorder=0)
    for router_idx, router in enumerate(routers):
        if router_idx > 0:
            ax_choice.axhline(router_idx * (len(SIGNALS) + 0.45) - 0.72, color="#D1D5DB", linewidth=1.0, zorder=0)
        for signal in SIGNALS:
            base_y = y_positions[(router, signal)]
            total = sum(direct_counts[(router, signal)].values())
            for worker in WORKERS:
                x = worker_x[worker]
                direct = direct_counts[(router, signal)][worker]
                calibrated = calibrated_counts[(router, signal)][worker]
                for count, dy, filled in [(direct, 0.15, False), (calibrated, -0.15, True)]:
                    if count <= 0:
                        continue
                    size = 45 + 520 * (count / max_count)
                    ax_choice.scatter(
                        [x],
                        [base_y + dy],
                        s=size,
                        facecolor=WORKER_COLORS[worker] if filled else "white",
                        edgecolor=WORKER_COLORS[worker],
                        linewidth=1.6,
                        alpha=0.93,
                        zorder=3,
                    )
                    ax_choice.text(
                        x,
                        base_y + dy,
                        str(count),
                        ha="center",
                        va="center",
                        fontsize=7.4,
                        color="white" if filled else WORKER_COLORS[worker],
                        fontweight="bold",
                        zorder=4,
                    )
            if total:
                ax_choice.text(
                    len(WORKERS) - 0.04,
                    base_y,
                    f"n={total}",
                    ha="left",
                    va="center",
                    fontsize=7,
                    color="#6B7280",
                )

    y_ticks = [y_positions[(router, signal)] for router in routers for signal in SIGNALS]
    ax_choice.set_yticks(y_ticks)
    ax_choice.set_yticklabels(y_labels, fontsize=8)
    ax_choice.set_xticks(list(worker_x.values()))
    ax_choice.set_xticklabels([WORKER_LABELS[worker] for worker in WORKERS], fontsize=9)
    ax_choice.set_xlim(-0.55, len(WORKERS) - 0.02)
    ax_choice.set_ylim(max(y_ticks) + 0.55, -0.55)
    ax_choice.set_title("B. Hard choice versus lookup choice", loc="left", fontweight="bold")
    ax_choice.set_xlabel("Selected agent system")
    ax_choice.grid(axis="x", alpha=0.0)
    ax_choice.grid(axis="y", alpha=0.18)
    ax_choice.spines[["top", "right"]].set_visible(False)

    worker_handles = [
        plt.Rectangle((0, 0), 1, 1, color=WORKER_COLORS[worker], label=f"{WORKER_LABELS[worker]} = {WORKER_LONG_LABELS[worker]}")
        for worker in WORKERS
    ]
    decision_handles = [
        plt.Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="white", markeredgecolor="#111827", markeredgewidth=1.6, markersize=8, label="direct router choice"),
        plt.Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="#111827", markeredgecolor="#111827", markersize=8, label="lookup-calibrated choice"),
    ]
    fig.legend(handles=worker_handles + decision_handles, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.59, 0.045), fontsize=8)
    fig.suptitle("Mode recognition shifts cleanly; lookup stabilizes worker choice", fontsize=14, fontweight="bold", y=0.985)
    fig.subplots_adjust(left=0.06, right=0.985, bottom=0.24, top=0.88, wspace=0.28)
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
