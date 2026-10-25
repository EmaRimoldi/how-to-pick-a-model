"""Generate figures for the evaluation-protocol calibration experiment."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


STUDY = Path(__file__).resolve().parents[1]
RESULTS = STUDY / "results"
FIGURES = RESULTS / "figures"
FIXED_TIME = RESULTS / "fixed_time_cpu_scaling" / "fixed_time_summary.csv"
FIXED_STEP = RESULTS / "fixed_step_cpu_pair_benchmark" / "fixed_step_summary.csv"

BLUE = "#2563eb"
ORANGE = "#f97316"
GREEN = "#16a34a"
GRAY = "#64748b"
DARK = "#111827"
GRID = "#e5e7eb"


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": DARK,
            "axes.titlecolor": DARK,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "legend.frameon": False,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.png", dpi=220)
    fig.savefig(FIGURES / f"{stem}.pdf")
    plt.close(fig)


def fixed_time_series(df: pd.DataFrame, policy: str) -> pd.DataFrame:
    baseline = df[df["condition"] == "single_sequential"]
    policy_rows = df[df["policy"] == policy]
    return pd.concat([baseline, policy_rows], ignore_index=True).sort_values("n")


def figure_fixed_time_compute_loss() -> None:
    df = pd.read_csv(FIXED_TIME)
    default = fixed_time_series(df, "default")
    partitioned = fixed_time_series(df, "partitioned")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), constrained_layout=True)

    ax = axes[0]
    ax.plot(default["n"], default["mean_steps"], marker="o", linewidth=2.4, color=BLUE, label="default threads")
    ax.plot(
        partitioned["n"],
        partitioned["mean_steps"],
        marker="s",
        linewidth=2.4,
        color=ORANGE,
        label="partitioned cores",
    )
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1", "2", "4", "8"])
    ax.set_xlabel("Concurrent training processes")
    ax.set_ylabel("Optimizer updates completed per worker")
    ax.set_title("A. Fixed time: workers complete fewer updates")
    ax.set_ylim(0, 23)
    ax.legend(loc="upper right")

    ax = axes[1]
    ax.plot(default["n"], default["mean_val_bpb"], marker="o", linewidth=2.4, color=BLUE, label="default threads")
    ax.plot(
        partitioned["n"],
        partitioned["mean_val_bpb"],
        marker="s",
        linewidth=2.4,
        color=ORANGE,
        label="partitioned cores",
    )
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1", "2", "4", "8"])
    ax.set_xlabel("Concurrent training processes")
    ax.set_ylabel("Validation loss after fixed-time training")
    ax.set_title("B. Fewer updates show up as worse validation loss")
    ax.set_ylim(1.90, 2.24)
    ax.text(0.02, 0.94, "lower is better", transform=ax.transAxes, color=GRAY)

    fig.suptitle("Fixed-time evaluation confounds agent quality with compute allocation", fontsize=15, y=1.04)
    save(fig, "figure-01-fixed-time-compute-loss")


def figure_fixed_step_latency_cost() -> None:
    df = pd.read_csv(FIXED_STEP)
    labels = ["1 proc\n4 threads", "2 seq\n4 threads", "2 parallel\n4 threads", "2 parallel\n2 threads"]
    colors = [GRAY, "#94a3b8", BLUE, ORANGE]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), constrained_layout=True)

    ax = axes[0]
    bars = ax.bar(labels, df["group_wall_seconds"], color=colors)
    ax.set_title("A. Group wall time")
    ax.set_ylabel("Seconds")
    ax.grid(axis="x", visible=False)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 4, f"{bar.get_height():.0f}s", ha="center")
    ax.set_ylim(0, 190)

    ax = axes[1]
    bars = ax.bar(labels, df["mean_worker_wall_seconds"], color=colors)
    ax.set_title("B. Mean time per worker")
    ax.set_ylabel("Seconds")
    ax.grid(axis="x", visible=False)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 4, f"{bar.get_height():.0f}s", ha="center")
    ax.set_ylim(0, 140)

    ax = axes[2]
    ax.plot(labels, df["mean_val_bpb"], marker="o", linewidth=2.4, color=GREEN)
    ax.set_title("C. Quality stays fixed when steps are fixed")
    ax.set_ylabel("Validation loss")
    ax.set_ylim(1.24, 1.30)
    ax.grid(axis="x", visible=False)
    for idx, value in enumerate(df["mean_val_bpb"]):
        ax.text(idx, value + 0.004, f"{value:.6f}", ha="center", fontsize=9)

    for ax in axes:
        ax.tick_params(axis="x", labelrotation=0)

    fig.suptitle("Fixed-step evaluation separates quality from latency", fontsize=15, y=1.04)
    save(fig, "figure-02-fixed-step-latency-cost")


def figure_fixed_time_throughput_efficiency() -> None:
    df = pd.read_csv(FIXED_TIME)
    default = fixed_time_series(df, "default")
    partitioned = fixed_time_series(df, "partitioned")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), constrained_layout=True)

    ax = axes[0]
    ax.plot([1, 2, 4, 8], [1, 2, 4, 8], linestyle="--", linewidth=1.6, color="#94a3b8", label="ideal linear")
    ax.plot(default["n"], default["speedup"], marker="o", linewidth=2.4, color=BLUE, label="default threads")
    ax.plot(partitioned["n"], partitioned["speedup"], marker="s", linewidth=2.4, color=ORANGE, label="partitioned cores")
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1", "2", "4", "8"])
    ax.set_xlabel("Concurrent training processes")
    ax.set_ylabel("Group speedup")
    ax.set_title("A. More workers increase throughput sublinearly")
    ax.legend(loc="upper left")

    ax = axes[1]
    ax.plot(default["n"], default["efficiency"] * 100, marker="o", linewidth=2.4, color=BLUE, label="default threads")
    ax.plot(
        partitioned["n"],
        partitioned["efficiency"] * 100,
        marker="s",
        linewidth=2.4,
        color=ORANGE,
        label="partitioned cores",
    )
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1", "2", "4", "8"])
    ax.set_xlabel("Concurrent training processes")
    ax.set_ylabel("Parallel efficiency (%)")
    ax.set_title("B. Efficiency falls as workers contend for CPU")
    ax.set_ylim(0, 110)

    fig.suptitle("Compute allocation sets the real capacity of parallel evaluation", fontsize=15, y=1.04)
    save(fig, "figure-03-throughput-efficiency")


def main() -> None:
    style()
    figure_fixed_time_compute_loss()
    figure_fixed_step_latency_cost()
    figure_fixed_time_throughput_efficiency()


if __name__ == "__main__":
    main()
