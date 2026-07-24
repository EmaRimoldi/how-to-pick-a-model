"""Generate a simple visual map of the repository experiments."""

from __future__ import annotations

from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "assets" / "experiments"

DARK = "#111827"
GRAY = "#64748b"
BLUE = "#2563eb"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
RED = "#dc2626"
FILL = "#f8fafc"

EXPERIMENTS = [
    {
        "name": "Baseline",
        "folder": "01_baseline/",
        "role": "Choose the common starting train.py",
        "result": "161 controlled evaluations; selected val_bpb 0.841",
        "color": BLUE,
    },
    {
        "name": "Evaluation protocol",
        "folder": "02_evaluation_protocol_calibration/",
        "role": "Make evaluation deterministic and hardware-aware",
        "result": "Fixed steps remove noise; fixed time exposes contention",
        "color": ORANGE,
    },
    {
        "name": "Agent memory ablation",
        "folder": "03_agent_memory_ablation/",
        "role": "Test memory and exploration",
        "result": "T07 was better and more stable than T06",
        "color": PURPLE,
    },
    {
        "name": "Swarm baselines",
        "folder": "04_swarm_baselines/",
        "role": "Preserve blackboard coordination evidence",
        "result": "Historical swarm runs beat independent parallel baseline",
        "color": RED,
    },
]


def wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


def add_box(ax: plt.Axes, x: float, y: float, item: dict) -> None:
    box = FancyBboxPatch(
        (x, y),
        2.62,
        1.34,
        boxstyle="round,pad=0.035,rounding_size=0.05",
        facecolor=FILL,
        edgecolor=item["color"],
        linewidth=1.5,
    )
    ax.add_patch(box)
    ax.text(x + 1.31, y + 1.16, item["name"], ha="center", va="top", fontsize=12, fontweight="bold", color=DARK)
    ax.text(x + 1.31, y + 0.86, item["folder"], ha="center", va="top", fontsize=9.5, color=item["color"])
    ax.text(x + 1.31, y + 0.61, wrap(item["role"], 31), ha="center", va="top", fontsize=9.5, color="#374151")
    ax.text(x + 1.31, y + 0.26, wrap(item["result"], 34), ha="center", va="top", fontsize=8.7, color=GRAY)


def arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=1.4,
            color="#94a3b8",
            shrinkA=3,
            shrinkB=3,
        )
    )


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13.8, 5.9), constrained_layout=True)
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.0)
    ax.set_title("Experiment map: what each experiment contributes", fontsize=17, pad=14, color=DARK)

    positions = [(0.35, 3.0), (3.65, 3.0), (6.95, 3.0), (3.65, 0.9)]
    for item, (x, y) in zip(EXPERIMENTS, positions):
        add_box(ax, x, y, item)

    arrow(ax, (2.97, 3.67), (3.65, 3.67))
    arrow(ax, (6.27, 3.67), (6.95, 3.67))
    arrow(ax, (8.26, 3.0), (4.96, 2.24))

    ax.text(
        5.0,
        0.22,
        "Read left-to-right for methodology, then current agent evidence, then historical swarm context.",
        ha="center",
        fontsize=10.5,
        color=GRAY,
    )

    fig.savefig(FIGURES / "experiment-map.png", dpi=260)
    fig.savefig(FIGURES / "experiment-map.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
