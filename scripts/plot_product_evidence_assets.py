"""Generate README product assets from checked-in experiment evidence."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "docs" / "assets" / "product"
RAW_ROOT = ROOT / "experiments" / "autoresearch" / "05_autoresearch_model_routing" / "raw"
MEMORY_RESULTS = (
    ROOT
    / "experiments"
    / "autoresearch"
    / "03_agent_memory_ablation"
    / "results"
    / "trial_results.json"
)

WORKER_LABELS = {
    "gpt_5_3_codex": "Worker A",
    "gpt_5_4": "Worker B",
    "gpt_5_4_mini": "Worker C",
}
WORKER_COLORS = {
    "gpt_5_3_codex": "#00A6FF",
    "gpt_5_4": "#7C3AED",
    "gpt_5_4_mini": "#F97316",
}
WORKFLOW_COLORS = {
    "Single": "#0891B2",
    "Exploratory": "#F97316",
    "No memory": "#DC2626",
    "Shared memory": "#16A34A",
}


def load_progress() -> dict[str, np.ndarray]:
    inventory = RAW_ROOT / "manifests" / "raw_run_inventory.csv"
    traces: dict[str, list[list[float]]] = defaultdict(list)
    with inventory.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["in_balanced_n30_manifest"] != "yes" or row["steps_completed"] != "20":
                continue
            worker = row["model_alias"]
            eval_path = RAW_ROOT / row["source_type"] / row["run_id"] / "evaluations.jsonl"
            if not eval_path.exists():
                continue
            values: list[float] = []
            with eval_path.open(encoding="utf-8") as evals:
                for line in evals:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    # Convert relative improvement to a normalized loss-like curve.
                    # 1.0 means no improvement over the starting candidate.
                    values.append(1.0 - float(record["relative_improvement_so_far"]))
            if len(values) == 20:
                traces[worker].append(values)
    return {worker: np.asarray(values, dtype=float) for worker, values in traces.items()}


def load_workflow_rows() -> list[dict[str, object]]:
    rows = json.loads(MEMORY_RESULTS.read_text(encoding="utf-8"))["trials"]
    by_id = {row["trial_id"]: row for row in rows}
    selected = [
        ("Single", "T02", "single agent"),
        ("Exploratory", "T06", "no shared memory"),
        ("No memory", "T08", "two exploratory agents"),
        ("Shared memory", "T07", "two exploratory agents"),
    ]
    output: list[dict[str, object]] = []
    for label, trial_id, note in selected:
        row = by_id[trial_id]
        output.append(
            {
                "label": label,
                "trial_id": trial_id,
                "note": note,
                "budget": row["budget_minutes"],
                "attempts": row["training_attempts"],
                "best": row["best_val_bpb"],
                "mean": row["mean_val_bpb"],
                "worst": row["worst_val_bpb"],
            }
        )
    return output


def style_axis(ax: plt.Axes) -> None:
    ax.set_facecolor("#f8fafc")
    ax.grid(True, axis="y", color="#dbe4ee", linewidth=0.8)
    ax.grid(True, axis="x", color="#eef2f7", linewidth=0.55)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors="#334155", labelsize=9)


def render_frame(
    progress: dict[str, np.ndarray],
    workflow_rows: list[dict[str, object]],
    current_step: int,
    *,
    save_static: bool = False,
) -> Image.Image:
    steps = np.arange(1, 21)
    fig = plt.figure(figsize=(14, 7.8), dpi=170)
    fig.patch.set_facecolor("#f8fafc")
    gs = fig.add_gridspec(2, 2, width_ratios=(1.65, 1.0), height_ratios=(1.22, 0.78), wspace=0.25, hspace=0.3)
    ax_curve = fig.add_subplot(gs[0, 0])
    ax_delta = fig.add_subplot(gs[1, 0])
    ax_workflow = fig.add_subplot(gs[:, 1])

    fig.suptitle(
        "AutoResearch orchestration evidence",
        x=0.06,
        y=0.985,
        ha="left",
        fontsize=18.5,
        fontweight="bold",
        color="#0f172a",
    )
    fig.text(
        0.06,
        0.94,
        "Step-level curves use 180 raw traces; workflow bars use aggregate memory-ablation trials.",
        ha="left",
        fontsize=10.2,
        color="#475569",
    )

    style_axis(ax_curve)
    ax_curve.set_title("Normalized validation loss over proposal steps", loc="left", fontsize=12.5, fontweight="bold", color="#0f172a")
    ax_curve.set_xlabel("proposal/evaluation step", color="#334155")
    ax_curve.set_ylabel("normalized loss (lower is better)", color="#334155")
    ax_curve.set_xlim(1, 20)
    ax_curve.set_ylim(0.62, 1.005)
    ax_curve.set_xticks([1, 5, 10, 15, 20])

    style_axis(ax_delta)
    ax_delta.set_title("Mean step-to-step change", loc="left", fontsize=12.5, fontweight="bold", color="#0f172a")
    ax_delta.set_xlabel("proposal/evaluation step", color="#334155")
    ax_delta.set_ylabel("delta loss", color="#334155")
    ax_delta.axhline(0, color="#64748b", lw=1)
    ax_delta.set_xlim(2, 20)
    ax_delta.set_ylim(-0.045, 0.015)
    ax_delta.set_xticks([2, 5, 10, 15, 20])

    for worker, arr in sorted(progress.items()):
        mean = arr.mean(axis=0)
        p25 = np.percentile(arr, 25, axis=0)
        p75 = np.percentile(arr, 75, axis=0)
        color = WORKER_COLORS.get(worker, "#2563eb")
        label = WORKER_LABELS.get(worker, worker)
        end = current_step
        ax_curve.plot(steps[:end], mean[:end], color=color, lw=2.8, label=label)
        ax_curve.fill_between(steps[:end], p25[:end], p75[:end], color=color, alpha=0.12, linewidth=0)
        if end > 1:
            delta = np.diff(mean)
            ax_delta.plot(steps[1:end], delta[: end - 1], color=color, lw=2.3, label=label)

    ax_curve.legend(loc="lower left", frameon=False, fontsize=9.5)

    style_axis(ax_workflow)
    ax_workflow.set_title("Workflow ablation summary", loc="left", fontsize=12.5, fontweight="bold", color="#0f172a")
    labels = [str(row["label"]) for row in workflow_rows]
    means = [float(row["mean"]) for row in workflow_rows]
    bests = [float(row["best"]) for row in workflow_rows]
    worsts = [float(row["worst"]) for row in workflow_rows]
    y = np.arange(len(labels))
    colors = [WORKFLOW_COLORS[label] for label in labels]
    left = np.minimum(bests, means)
    right = np.maximum(worsts, means)
    ax_workflow.barh(y, means, color=colors, alpha=0.88, height=0.52)
    ax_workflow.errorbar(
        means,
        y,
        xerr=[np.asarray(means) - np.asarray(bests), np.asarray(worsts) - np.asarray(means)],
        fmt="none",
        ecolor="#334155",
        elinewidth=1.4,
        capsize=3,
        alpha=0.75,
    )
    ax_workflow.scatter(bests, y, color="#0f172a", s=28, zorder=5, label="best")
    ax_workflow.set_yticks(y, labels)
    ax_workflow.invert_yaxis()
    ax_workflow.set_xlabel("validation BPB (lower is better)", color="#334155")
    ax_workflow.set_xlim(0.80, max(right) + 0.35)
    ax_workflow.grid(True, axis="x", color="#dbe4ee", linewidth=0.8)
    ax_workflow.grid(False, axis="y")
    for idx, row in enumerate(workflow_rows):
        ax_workflow.text(
            0.82,
            idx + 0.34,
            f"{row['trial_id']} - {row['budget']} min - {row['attempts']} attempts",
            fontsize=8.7,
            color="#475569",
            va="center",
        )
        ax_workflow.text(
            means[idx] + 0.035,
            idx,
            f"mean {means[idx]:.3f}",
            fontsize=9.5,
            color="#0f172a",
            va="center",
        )
    ax_workflow.text(
        0.82,
        len(labels) - 0.02,
        "Bars are not step curves: they summarize completed workflow trials.",
        fontsize=8.8,
        color="#64748b",
        va="bottom",
    )

    fig.subplots_adjust(left=0.07, right=0.965, top=0.86, bottom=0.105, wspace=0.25, hspace=0.38)
    if save_static:
        PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
        fig.savefig(PRODUCT_DIR / "autoresearch-orchestration-loss.png", bbox_inches="tight", pad_inches=0.14)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main() -> None:
    PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
    progress = load_progress()
    workflow_rows = load_workflow_rows()
    frames = []
    for step in range(1, 21):
        frames.append(render_frame(progress, workflow_rows, step, save_static=(step == 20)))
    frames[0].save(
        PRODUCT_DIR / "demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=130,
        loop=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
