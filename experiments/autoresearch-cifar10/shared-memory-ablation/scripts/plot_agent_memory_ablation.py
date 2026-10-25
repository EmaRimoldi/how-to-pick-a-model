"""Generate public figures for the agent memory ablation experiment."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


STUDY = Path(__file__).resolve().parents[1]
RESULTS = STUDY / "results" / "trial_results.json"
FIGURES = STUDY / "results" / "figures"

BASELINE_BPB = 0.925845

BLUE = "#2563eb"
GREEN = "#16a34a"
PURPLE = "#7c3aed"
TEAL = "#0891b2"
RED = "#dc2626"
GRAY = "#64748b"
LIGHT_GRAY = "#e2e8f0"
DARK = "#111827"

COLORS = {
    "no_memory": BLUE,
    "shared_memory": GREEN,
    "seeded": PURPLE,
    "shared_private": TEAL,
}


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
            "grid.color": LIGHT_GRAY,
            "grid.linewidth": 0.8,
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 14,
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


def load_trials() -> list[dict]:
    return json.loads(RESULTS.read_text())["trials"]


def save(fig: plt.Figure, stem: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{stem}.png", dpi=260)
    fig.savefig(FIGURES / f"{stem}.pdf")
    plt.close(fig)


def trial_by_id(trials: list[dict], trial_id: str) -> dict:
    for trial in trials:
        if trial["trial_id"] == trial_id:
            return trial
    raise KeyError(trial_id)


def label_for(trial: dict) -> str:
    return f"{trial['trial_id']}: {trial['condition']}\n{trial['budget_minutes']} min"


def figure_trial_outcomes(trials: list[dict]) -> None:
    y = list(range(len(trials)))

    fig, ax = plt.subplots(figsize=(11.4, 7.0), constrained_layout=True)
    ax.axvline(
        BASELINE_BPB,
        color=RED,
        linestyle="--",
        linewidth=1.8,
        label="baseline to beat",
    )

    for idx, trial in enumerate(trials):
        value = trial["best_val_bpb"]
        color = COLORS[trial["group"]]
        ax.hlines(
            idx,
            xmin=min(value, BASELINE_BPB),
            xmax=max(value, BASELINE_BPB),
            color=LIGHT_GRAY,
            linewidth=2,
        )
        marker = "*" if value < BASELINE_BPB else "o"
        size = 150 if marker == "*" else 90
        ax.scatter(
            value,
            idx,
            s=size,
            marker=marker,
            color=color,
            edgecolor="white",
            linewidth=1.0,
            zorder=3,
        )
        ax.text(value + 0.006, idx, f"{value:.3f}", va="center", fontsize=9.5, color=DARK)

    ax.set_yticks(y)
    ax.set_yticklabels([label_for(trial) for trial in trials])
    ax.invert_yaxis()
    ax.set_xlim(0.86, 1.14)
    ax.set_xlabel("Best validation BPB reached (lower is better)")
    ax.set_title("Valid trial outcomes")
    ax.grid(axis="y", visible=False)

    handles = [
        plt.Line2D([0], [0], color=RED, linestyle="--", linewidth=1.8, label="baseline"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, markersize=9, label="no memory"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=GREEN, markersize=9, label="shared memory"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=TEAL, markersize=9, label="shared + private memory"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=PURPLE, markersize=9, label="seeded"),
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor=DARK, markersize=12, label="beat baseline"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=9)

    save(fig, "figure-01-trial-outcomes")


def figure_memory_stabilization(trials: list[dict]) -> None:
    trial_ids = ["T06", "T07", "T04", "T08"]
    selected = [trial_by_id(trials, trial_id) for trial_id in trial_ids]
    labels = [
        "T06\nexploratory\nno memory",
        "T07\nexploratory\nshared memory",
        "T04\nmixed style\nno memory",
        "T08\ntwo exploratory\nno memory",
    ]
    colors = [COLORS[trial["group"]] for trial in selected]
    mean_values = [trial["mean_val_bpb"] for trial in selected]
    best_values = [trial["best_val_bpb"] for trial in selected]
    worst_values = [trial["worst_val_bpb"] for trial in selected]
    attempts = [trial["training_attempts"] for trial in selected]

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.2), constrained_layout=True)

    ax = axes[0]
    x = range(len(selected))
    width = 0.34
    ax.bar(
        [i - width / 2 for i in x],
        mean_values,
        width=width,
        color=colors,
        alpha=0.78,
        label="mean",
    )
    ax.scatter(
        [i + width / 2 for i in x],
        best_values,
        s=130,
        marker="*",
        color=colors,
        edgecolor="white",
        linewidth=1.0,
        label="best",
    )
    ax.axhline(BASELINE_BPB, color=RED, linestyle="--", linewidth=1.6, label="baseline")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Validation BPB")
    ax.set_title("Shared memory keeps exploratory agents near the baseline")
    ax.set_ylim(0.84, 2.02)
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(axis="x", visible=False)

    for i, (mean, best) in enumerate(zip(mean_values, best_values)):
        ax.text(i - width / 2, mean + 0.035, f"{mean:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, best - 0.055, f"{best:.3f}", ha="center", fontsize=9)

    ax = axes[1]
    ax.bar(labels, worst_values, color=colors, alpha=0.82)
    ax.set_ylabel("Worst validation BPB")
    ax.set_title("Shared memory reduces catastrophic outcomes")
    ax.set_ylim(0, 8.4)
    ax.grid(axis="x", visible=False)
    for i, (value, n) in enumerate(zip(worst_values, attempts)):
        ax.text(i, value + 0.16, f"{value:.2f}\n{n} attempts", ha="center", fontsize=9.5)

    fig.text(
        0.5,
        -0.02,
        "T06/T07/T08 use exploratory prompt style for 45 minutes; T04 is a shorter mixed-style no-memory reference.",
        ha="center",
        fontsize=9.4,
        color=GRAY,
    )

    save(fig, "figure-02-memory-stabilization")


def figure_training_attempts(trials: list[dict]) -> None:
    labels = [trial["trial_id"] for trial in trials]
    counts = [trial["training_attempts"] for trial in trials]
    colors = [COLORS[trial["group"]] for trial in trials]

    fig, ax = plt.subplots(figsize=(10.8, 4.8), constrained_layout=True)
    x = range(len(trials))
    ax.bar(x, counts, color=colors, alpha=0.86)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Training attempts")
    ax.set_title("How many attempts each valid trial produced")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="x", visible=False)

    for i, value in enumerate(counts):
        ax.text(i, value + 0.7, str(value), ha="center", fontsize=10, color=DARK)

    fig.text(
        0.5,
        -0.02,
        "Only renumbered valid trials T01-T11 are shown. Corrupted or non-executed historical cells are not part of this dataset.",
        ha="center",
        fontsize=9.4,
        color=GRAY,
    )

    save(fig, "figure-03-training-attempts")


def main() -> None:
    style()
    trials = load_trials()
    figure_trial_outcomes(trials)
    figure_memory_stabilization(trials)
    figure_training_attempts(trials)


if __name__ == "__main__":
    main()
