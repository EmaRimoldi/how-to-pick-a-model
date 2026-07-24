"""Generate public figures for the historical swarm baseline experiment."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "experiments" / "autoresearch" / "04_swarm_baselines"
FIGURES = STUDY / "results" / "figures"

BLUE = "#2563eb"
ORANGE = "#f97316"
GREEN = "#16a34a"
PURPLE = "#7c3aed"
RED = "#dc2626"
SLATE = "#334155"
MUTED = "#64748b"
GRID = "#e2e8f0"
DARK = "#111827"
PAPER = "#f8fafc"

MODEL_BASELINE_BPB = 1.1020746984708296
INDEPENDENT_PARALLEL_BPB = 1.113130

SWARM_RUNS = [
    {
        "label": "Haiku run 1",
        "model": "Haiku 4.5",
        "best_bpb": 1.041477,
        "runs": 27,
        "duration_min": 119.2,
        "color": ORANGE,
    },
    {
        "label": "Haiku run 2",
        "model": "Haiku 4.5",
        "best_bpb": 1.044341,
        "runs": 28,
        "duration_min": 120.0,
        "color": "#fb923c",
    },
    {
        "label": "Sonnet",
        "model": "Sonnet 4.6",
        "best_bpb": 1.044216,
        "runs": 29,
        "duration_min": 124.8,
        "color": BLUE,
    },
    {
        "label": "Opus",
        "model": "Opus 4.6",
        "best_bpb": 1.044304,
        "runs": 22,
        "duration_min": 119.7,
        "color": PURPLE,
    },
]


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": DARK,
            "axes.titlecolor": DARK,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "legend.frameon": True,
            "legend.facecolor": "white",
            "legend.edgecolor": "#cbd5e1",
            "legend.framealpha": 0.96,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.png", dpi=260)
    fig.savefig(FIGURES / f"{stem}.pdf")
    plt.close(fig)


def add_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    color: str,
    fill: str = "white",
) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.025,rounding_size=0.055",
        linewidth=1.5,
        edgecolor=color,
        facecolor=fill,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h - 0.17,
        title,
        ha="center",
        va="top",
        fontsize=12,
        fontweight="bold",
        color=DARK,
    )
    ax.text(
        x + w / 2,
        y + h - 0.47,
        body,
        ha="center",
        va="top",
        fontsize=10,
        color="#374151",
        linespacing=1.25,
    )


def add_arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    both: bool = False,
    dashed: bool = False,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="<->" if both else "-|>",
            mutation_scale=17,
            linewidth=1.8,
            linestyle="--" if dashed else "-",
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def figure_validation_bpb_over_time() -> None:
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(13.4, 5.25),
        constrained_layout=True,
        gridspec_kw={"width_ratios": [1.18, 0.82]},
    )

    ax = axes[0]
    ax.axhline(
        INDEPENDENT_PARALLEL_BPB,
        color=RED,
        linestyle="--",
        linewidth=1.6,
        label="independent parallel best",
    )
    ax.axhline(
        MODEL_BASELINE_BPB,
        color=MUTED,
        linestyle=":",
        linewidth=1.9,
        label="initial candidate BPB",
    )

    for run in SWARM_RUNS:
        ax.plot(
            [0, run["duration_min"]],
            [MODEL_BASELINE_BPB, run["best_bpb"]],
            color=run["color"],
            linewidth=2.4,
            marker="o",
            markersize=6.2,
            label=run["label"],
        )
        ax.scatter(
            run["duration_min"],
            run["best_bpb"],
            s=105,
            color=run["color"],
            edgecolor="white",
            linewidth=1.0,
            zorder=4,
        )

    ax.set_title("Validation BPB reached within the two-hour swarm budget")
    ax.set_xlabel("Minutes from run start")
    ax.set_ylabel("Best validation BPB reached (lower is better)")
    ax.set_xlim(-3, 130)
    ax.set_ylim(1.035, 1.122)
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[1]
    for run in SWARM_RUNS:
        ax.scatter(
            run["runs"],
            run["best_bpb"],
            s=150,
            color=run["color"],
            edgecolor="white",
            linewidth=1.0,
            label=run["label"],
        )

    label_offsets = {
        "Haiku run 1": (0.35, -0.0042),
        "Haiku run 2": (-1.15, 0.0030),
        "Sonnet": (-0.10, 0.0030),
        "Opus": (0.42, 0.0030),
    }
    for run in SWARM_RUNS:
        dx, dy = label_offsets[run["label"]]
        ax.text(
            run["runs"] + dx,
            run["best_bpb"] + dy,
            run["label"],
            fontsize=9.5,
            color="#374151",
        )

    ax.axhline(INDEPENDENT_PARALLEL_BPB, color=RED, linestyle="--", linewidth=1.6)
    ax.set_title("Same budget, different number of valid attempts")
    ax.set_xlabel("Successful training attempts")
    ax.set_ylabel("Best validation BPB reached")
    ax.set_xlim(19, 31)
    ax.set_ylim(1.035, 1.122)

    fig.text(
        0.5,
        -0.025,
        "The four model-comparison artifacts track final best values, durations, and attempt counts; raw per-trial validation curves are not available for all runs.",
        ha="center",
        fontsize=9.4,
        color=MUTED,
    )

    save(fig, "figure-01-validation-bpb-over-time")


def figure_swarm_memory_architecture() -> None:
    fig, ax = plt.subplots(figsize=(12.7, 5.7), constrained_layout=True)
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.set_title("Swarm mode: two isolated agents coordinate through one blackboard", fontsize=16, pad=14)

    add_box(
        ax,
        3.35,
        4.78,
        3.30,
        0.82,
        "Orchestrator",
        "spawns two Claude Code CLI subprocesses",
        SLATE,
        PAPER,
    )
    add_box(
        ax,
        0.48,
        2.83,
        2.45,
        1.40,
        "Agent 0",
        "isolated worktree\nGPU slot 0\ntraining attempts",
        BLUE,
    )
    add_box(
        ax,
        7.07,
        2.83,
        2.45,
        1.40,
        "Agent 1",
        "isolated worktree\nGPU slot 1\ntraining attempts",
        ORANGE,
    )
    add_box(
        ax,
        3.48,
        2.50,
        3.04,
        1.80,
        "Shared blackboard",
        "append-only JSONL\nclaims, results, best code\ninsights and hypotheses",
        GREEN,
        "#f0fdf4",
    )
    add_box(
        ax,
        3.46,
        0.60,
        3.08,
        1.12,
        "Task",
        "edit train.py, run evaluator,\nminimize validation BPB",
        SLATE,
        PAPER,
    )

    add_arrow(ax, (4.36, 4.78), (1.85, 4.23), BLUE)
    add_arrow(ax, (5.64, 4.78), (8.15, 4.23), ORANGE)
    add_arrow(ax, (2.93, 3.48), (3.48, 3.48), BLUE, both=True)
    add_arrow(ax, (7.07, 3.48), (6.52, 3.48), ORANGE, both=True)
    add_arrow(ax, (5.00, 2.50), (5.00, 1.72), GREEN)
    add_arrow(ax, (1.70, 2.83), (4.16, 1.72), BLUE)
    add_arrow(ax, (8.30, 2.83), (5.84, 1.72), ORANGE)

    ax.text(
        5.0,
        0.13,
        "Tracked setup: 1 GPU per agent, 2 GPUs total, 120 minutes per agent. Exact GPU model/type is not available in the curated artifacts.",
        ha="center",
        fontsize=9.7,
        color=MUTED,
    )

    save(fig, "figure-04-swarm-memory-architecture")


def figure_independent_parallel_architecture() -> None:
    fig, ax = plt.subplots(figsize=(12.7, 5.5), constrained_layout=True)
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.set_title("Independent parallel baseline: same task, no shared memory during the run", fontsize=16, pad=14)

    add_box(
        ax,
        3.40,
        4.78,
        3.20,
        0.82,
        "Orchestrator",
        "launches two independent workers",
        SLATE,
        PAPER,
    )
    add_box(
        ax,
        0.58,
        2.72,
        2.64,
        1.50,
        "Agent 0",
        "Claude Code subprocess\nprivate worktree\nown evaluator",
        BLUE,
    )
    add_box(
        ax,
        6.78,
        2.72,
        2.64,
        1.50,
        "Agent 1",
        "Claude Code subprocess\nprivate worktree\nown evaluator",
        ORANGE,
    )
    add_box(
        ax,
        3.55,
        2.86,
        2.90,
        1.18,
        "No mid-run channel",
        "no shared context\nno shared files\nno blackboard",
        RED,
        "#fef2f2",
    )
    add_box(
        ax,
        3.50,
        0.62,
        3.00,
        1.05,
        "Post-run collector",
        "compares final outputs\nafter both agents exit",
        SLATE,
        PAPER,
    )

    add_arrow(ax, (4.34, 4.78), (1.90, 4.22), BLUE)
    add_arrow(ax, (5.66, 4.78), (8.10, 4.22), ORANGE)
    add_arrow(ax, (1.90, 2.72), (4.25, 1.67), BLUE)
    add_arrow(ax, (8.10, 2.72), (5.75, 1.67), ORANGE)
    add_arrow(ax, (3.22, 3.44), (3.55, 3.44), RED, dashed=True)
    add_arrow(ax, (6.78, 3.44), (6.45, 3.44), RED, dashed=True)

    ax.text(
        5.0,
        0.12,
        "The baseline tests whether simple concurrency is enough; the collector cannot guide search while the agents are running.",
        ha="center",
        fontsize=9.7,
        color=MUTED,
    )

    save(fig, "figure-05-independent-parallel-architecture")


def main() -> None:
    style()
    figure_validation_bpb_over_time()
    figure_swarm_memory_architecture()
    figure_independent_parallel_architecture()


if __name__ == "__main__":
    main()
