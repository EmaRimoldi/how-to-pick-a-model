"""Generate README-facing AutoResearch figures from balanced raw traces."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "experiments" / "autoresearch-cifar10" / "three-worker-model-routing"
RAW = STUDY / "raw"
INVENTORY = RAW / "manifests" / "raw_run_inventory.csv"
RUNS = RAW / "worker_confirmation"
OUT = ROOT / "docs" / "assets" / "autoresearch"

THRESHOLD = 0.05
WORKLOADS = ["mlp_flat", "cnn_compact", "resnet_micro"]
WORKLOAD_LABELS = {
    "mlp_flat": "MLP",
    "cnn_compact": "CNN",
    "resnet_micro": "ResNet",
}
WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
WORKER_LABELS = {
    "gpt_5_3_codex": "GPT-5.3 Codex",
    "gpt_5_4": "GPT-5.4",
    "gpt_5_4_mini": "GPT-5.4 Mini",
}
WORKER_COLORS = {
    "gpt_5_3_codex": "#2563eb",
    "gpt_5_4": "#f97316",
    "gpt_5_4_mini": "#16a34a",
}
MODE_LABELS = {
    "layout": "Architecture",
    "topk": "Learning rate",
    "caching": "Regularization",
    "summaries": "Schedule/budget",
    "indexing": "Optimizer",
    "micro": "Small loop edits",
}
MODE_COLORS = {
    "layout": "#2563eb",
    "topk": "#f97316",
    "caching": "#16a34a",
    "summaries": "#7c3aed",
    "indexing": "#0891b2",
    "micro": "#64748b",
}

DARK = "#111827"
MUTED = "#64748b"
GRID = "#e2e8f0"
RED = "#dc2626"
GREEN = "#16a34a"
ORANGE = "#f97316"


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
            "font.size": 10.5,
            "axes.titlesize": 13,
            "axes.labelsize": 10.5,
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "legend.frameon": True,
            "legend.facecolor": "white",
            "legend.edgecolor": "#cbd5e1",
            "legend.framealpha": 0.96,
            "savefig.bbox": "tight",
        }
    )


def balanced_runs() -> list[dict[str, str]]:
    with INVENTORY.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row
        for row in rows
        if row["in_balanced_n30_manifest"] == "yes"
        and row["task_mode_true"] in WORKLOADS
        and row["model_alias"] in WORKERS
    ]


def load_step_records(run_id: str) -> list[dict]:
    path = RUNS / run_id / "evaluations.jsonl"
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def grouped_trajectories(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[list[float]]]:
    grouped: dict[tuple[str, str], list[list[float]]] = defaultdict(list)
    for row in rows:
        records = load_step_records(row["run_id"])
        trajectory = [max(0.0, float(record.get("relative_improvement_so_far") or 0.0)) for record in records]
        if len(trajectory) == 20:
            grouped[(row["task_mode_true"], row["model_alias"])].append(trajectory)
    return grouped


def first_success_steps(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[int | None]]:
    result: dict[tuple[str, str], list[int | None]] = defaultdict(list)
    for row in rows:
        first: int | None = None
        for record in load_step_records(row["run_id"]):
            step = int(record["step"]) + 1
            improvement = max(0.0, float(record.get("relative_improvement_so_far") or 0.0))
            if improvement >= THRESHOLD:
                first = step
                break
        result[(row["task_mode_true"], row["model_alias"])].append(first)
    return result


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=260)
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def figure_progress_over_steps(rows: list[dict[str, str]]) -> None:
    grouped = grouped_trajectories(rows)
    steps = np.arange(1, 21)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.25), sharey=True, constrained_layout=True)

    for ax, workload in zip(axes, WORKLOADS):
        for worker in WORKERS:
            trajectories = np.array(grouped[(workload, worker)], dtype=float)
            mean = trajectories.mean(axis=0)
            q25, q75 = np.percentile(trajectories, [25, 75], axis=0)
            color = WORKER_COLORS[worker]
            ax.plot(steps, mean, color=color, linewidth=2.3, label=WORKER_LABELS[worker])
            ax.fill_between(steps, q25, q75, color=color, alpha=0.13, linewidth=0)

        ax.axhline(THRESHOLD, color=RED, linestyle=":", linewidth=1.5)
        ax.set_title(WORKLOAD_LABELS[workload])
        ax.set_xlabel("Proposal step")
        ax.set_xlim(1, 20)
        ax.set_ylim(0, 0.44)
        ax.set_xticks([1, 5, 10, 15, 20])
        ax.grid(axis="x", visible=False)

    axes[0].set_ylabel("Best relative validation-loss improvement")
    axes[-1].legend(loc="lower right", fontsize=9)
    fig.suptitle("AutoResearch improves over repeated proposals", fontsize=15, y=1.04)
    fig.text(
        0.5,
        -0.03,
        "Balanced raw subset only: 180 runs, 20 proposal/evaluation steps per run. Shaded bands show the interquartile range.",
        ha="center",
        fontsize=9.2,
        color=MUTED,
    )
    save(fig, "autoresearch-progress-over-steps")


def figure_first_success_by_step(rows: list[dict[str, str]]) -> None:
    grouped = first_success_steps(rows)
    steps = np.arange(1, 21)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.25), sharey=True, constrained_layout=True)

    for ax, workload in zip(axes, WORKLOADS):
        for worker in WORKERS:
            values = grouped[(workload, worker)]
            curve = [sum(first is not None and first <= step for first in values) / len(values) for step in steps]
            ax.step(
                steps,
                curve,
                where="post",
                color=WORKER_COLORS[worker],
                linewidth=2.4,
                label=WORKER_LABELS[worker],
            )
        ax.set_title(WORKLOAD_LABELS[workload])
        ax.set_xlabel("Proposal step")
        ax.set_xlim(1, 20)
        ax.set_ylim(0, 1.04)
        ax.set_xticks([1, 5, 10, 15, 20])
        ax.grid(axis="x", visible=False)

    axes[0].set_ylabel("Fraction of runs with >=5% improvement")
    axes[-1].legend(loc="lower right", fontsize=9)
    fig.suptitle("How quickly runs find a useful edit", fontsize=15, y=1.04)
    fig.text(
        0.5,
        -0.03,
        "A run counts as successful after its best validation loss improves by at least 5% relative to its starting script.",
        ha="center",
        fontsize=9.2,
        color=MUTED,
    )
    save(fig, "autoresearch-first-success-by-step")


def selected_candidate_delta(record: dict) -> float | None:
    parent = float(record.get("parent_latent_loss") or 0.0)
    if parent <= 0:
        return None
    selected = None
    selected_branch = record.get("selected_branch")
    for branch in record.get("branches") or []:
        if branch.get("selected_as_visible") is True:
            selected = branch
            break
        if selected_branch and str(branch.get("file_path", "")).startswith(str(selected_branch)):
            selected = branch
    if selected is None and record.get("branches"):
        selected = record["branches"][0]
    if selected is None:
        return None
    loss = selected.get("latent_loss")
    correctness = bool(selected.get("correctness", True))
    if loss is None or not correctness:
        return None
    return (parent - float(loss)) / parent


def figure_improvement_regression_by_step(rows: list[dict[str, str]]) -> None:
    values_by_step: dict[int, list[float]] = {step: [] for step in range(1, 21)}
    for row in rows:
        for record in load_step_records(row["run_id"]):
            delta = selected_candidate_delta(record)
            if delta is None:
                continue
            values_by_step[int(record["step"]) + 1].append(delta)

    steps = np.arange(1, 21)
    improve_share = []
    regress_share = []
    for step in steps:
        values = values_by_step[int(step)]
        total = len(values)
        improve_share.append(sum(value > 0 for value in values) / total)
        regress_share.append(sum(value < 0 for value in values) / total)
    improve_share = np.array(improve_share)
    regress_share = np.array(regress_share)

    fig, ax = plt.subplots(figsize=(11.6, 4.9), constrained_layout=True)
    ax.axhline(0, color=DARK, linewidth=1.0)
    ax.bar(steps, improve_share, color=GREEN, alpha=0.86, width=0.68, label="proposal improved parent")
    ax.bar(steps, -regress_share, color=ORANGE, alpha=0.86, width=0.68, label="proposal regressed parent")
    ax.set_xlim(0.25, 20.75)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.set_xlabel("Proposal step")
    ax.set_ylabel("Share of selected proposals")
    ax.set_title("Each proposal can improve or regress the current candidate")
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{abs(value) * 100:.0f}%"))
    ax.set_ylim(-0.44, 0.86)

    ax.legend(
        handles=[
            plt.Line2D([0], [0], color=GREEN, linewidth=7, label="improved parent"),
            plt.Line2D([0], [0], color=ORANGE, linewidth=7, label="regressed parent"),
        ],
        loc="upper right",
        fontsize=9,
    )
    fig.text(
        0.5,
        -0.04,
        "The chart counts selected candidate edits, not best-so-far progress. Positive bars lowered validation loss relative to the parent; negative bars made it worse.",
        ha="center",
        fontsize=9.2,
        color=MUTED,
    )
    save(fig, "autoresearch-improvement-regression-per-step")


def figure_edit_mode_timeline(rows: list[dict[str, str]]) -> None:
    per_step: dict[int, Counter[str]] = {step: Counter() for step in range(1, 21)}
    for row in rows:
        for record in load_step_records(row["run_id"]):
            step = int(record["step"]) + 1
            mode = str(record.get("selected_mode") or "unknown")
            per_step[step][mode] += 1

    modes = ["layout", "topk", "caching", "summaries", "indexing", "micro"]
    steps = np.arange(1, 21)
    shares = []
    for mode in modes:
        values = []
        for step in steps:
            total = sum(per_step[int(step)].values())
            values.append(per_step[int(step)][mode] / total if total else 0.0)
        shares.append(values)

    fig, ax = plt.subplots(figsize=(11.4, 4.8), constrained_layout=True)
    ax.stackplot(
        steps,
        shares,
        labels=[MODE_LABELS[mode] for mode in modes],
        colors=[MODE_COLORS[mode] for mode in modes],
        alpha=0.86,
    )
    ax.set_xlim(1, 20)
    ax.set_ylim(0, 1)
    ax.set_xticks([1, 5, 10, 15, 20])
    ax.set_xlabel("Proposal step")
    ax.set_ylabel("Share of selected edit families")
    ax.set_title("What kinds of edits agents try as the search progresses")
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=9)
    ax.grid(axis="x", visible=False)
    fig.text(
        0.5,
        -0.12,
        "Counts are pooled across the 180 balanced raw runs. Labels are reader-facing names for the stored AutoResearch action modes.",
        ha="center",
        fontsize=9.2,
        color=MUTED,
    )
    save(fig, "autoresearch-edit-mode-timeline")


def main() -> None:
    style()
    rows = balanced_runs()
    expected = 3 * 3 * 20
    if len(rows) != expected:
        raise RuntimeError(f"expected {expected} balanced raw runs, found {len(rows)}")
    figure_progress_over_steps(rows)
    figure_first_success_by_step(rows)
    figure_improvement_regression_by_step(rows)
    figure_edit_mode_timeline(rows)


if __name__ == "__main__":
    main()
