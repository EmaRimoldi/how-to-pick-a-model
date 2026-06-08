"""Generate current snapshot plots for the AutoResearch CIFAR-10 campaign."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
CAMPAIGN_ROOT = PROJECT_ROOT / "autoresearch" / "campaigns" / "h20_delta005_20260505"
OUT_DIR = CAMPAIGN_ROOT / "figures" / "current_snapshot"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODE_ORDER = ["cnn_compact", "mlp_flat", "resnet_micro"]
MODE_LABELS = ["CNN", "MLP", "ResNet"]
WORKER_ORDER = ["gpt-5.3-codex", "gpt-5.4", "gpt-5.4-mini"]
WORKER_LABELS = ["GPT-5.3 Codex", "GPT-5.4", "GPT-5.4 Mini"]
WORKER_COLORS = {
    "gpt-5.3-codex": "#4c78a8",
    "gpt-5.4": "#f58518",
    "gpt-5.4-mini": "#54a24b",
}
N34_TOTAL_PER_CELL = 34
N34_PILOT_PER_CELL = 10
N34_HOLDOUT_PER_CELL = N34_TOTAL_PER_CELL - N34_PILOT_PER_CELL
THRESHOLD = 0.05

from autoresearch.analysis.autoresearch_cifar10_z_signal_ablation import FEATURE_SETS, evaluate_feature_set, load_records

plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "figure.titlesize": 12,
    }
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT_DIR / f"{name}.png", dpi=220, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def mode_from_run_id(run_id: str) -> str:
    if "_pilot_" in run_id:
        return run_id.split("_pilot_", 1)[1].split("_seed", 1)[0]
    if "_holdout_" in run_id:
        return run_id.split("_holdout_", 1)[1].split("_seed", 1)[0]
    return "unknown"


def normalize_worker(value: Any) -> str:
    raw = str(value)
    mapping = {
        "gpt_5_3_codex": "gpt-5.3-codex",
        "gpt-5.3-codex": "gpt-5.3-codex",
        "gpt_5_4": "gpt-5.4",
        "gpt-5.4": "gpt-5.4",
        "gpt_5_4_mini": "gpt-5.4-mini",
        "gpt-5.4-mini": "gpt-5.4-mini",
    }
    return mapping.get(raw, raw)


def load_runs(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(root.glob("*/run_summary.json")):
        run_dir = summary_path.parent
        summary = load_json(summary_path)
        manifest = load_json(run_dir / "run_manifest.json")
        run_id = str(summary.get("run_id") or run_dir.name)
        mode = str(manifest.get("task_mode_true") or mode_from_run_id(run_id))
        worker = normalize_worker(summary.get("model_id") or manifest.get("model_alias") or "unknown")
        rows.append(
            {
                "run_dir": run_dir,
                "run_id": run_id,
                "split": "holdout" if "_holdout_" in run_id else "pilot" if "_pilot_" in run_id else "unknown",
                "mode": mode,
                "worker": worker,
                "seed": manifest.get("instance_seed"),
                "success": bool(summary.get("success")),
                "tau_step": summary.get("tau_step"),
                "baseline_loss": float(summary.get("baseline_loss") or math.nan),
                "best_loss": float(summary.get("best_visible_loss") or math.nan),
                "relative_improvement": float(summary.get("best_visible_relative_improvement") or 0.0),
                "elapsed_wall_seconds": float(summary.get("elapsed_wall_seconds") or 0.0),
                "steps_completed": int(summary.get("steps_completed") or 0),
            }
        )
    return rows


def pooled_pilot_holdout_panel(
    rows: list[dict[str, Any]],
    pilot_per_cell: int = N34_PILOT_PER_CELL,
    holdout_per_cell: int = N34_HOLDOUT_PER_CELL,
) -> list[dict[str, Any]]:
    """Use the balanced three-worker 10 pilot + 24 holdout runs for each cell."""
    by_key: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for row in rows:
        if row["mode"] not in MODE_ORDER or row["worker"] not in WORKER_ORDER or row.get("seed") is None:
            continue
        key = (row["split"], row["mode"], row["worker"], int(row["seed"]))
        previous = by_key.get(key)
        if previous is None or str(row.get("run_id")) > str(previous.get("run_id")):
            by_key[key] = row

    selected: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        for worker in WORKER_ORDER:
            for split, limit in [("pilot", pilot_per_cell), ("holdout", holdout_per_cell)]:
                seeds = sorted(seed for s, m, w, seed in by_key if s == split and m == mode and w == worker)
                for seed in seeds[:limit]:
                    selected.append(by_key[(split, mode, worker, seed)])
    return selected


def rel_improvement(baseline: float, loss: float | None) -> float | None:
    if loss is None or not math.isfinite(loss) or baseline <= 0 or not math.isfinite(baseline):
        return None
    return (baseline - loss) / baseline


def trajectory(run: dict[str, Any]) -> tuple[list[int], list[float], list[float]]:
    eval_path = Path(run["run_dir"]) / "evaluations.jsonl"
    if not eval_path.exists():
        return [], [], []
    baseline = float(run["baseline_loss"])
    selected: list[float] = []
    best: list[float] = []
    running_best = baseline
    for raw in eval_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        selected_losses = [
            float(branch["latent_loss"])
            for branch in record.get("branches", [])
            if branch.get("promoted_as_parent") and branch.get("correctness") and branch.get("latent_loss") is not None
        ]
        selected_loss = min(selected_losses) if selected_losses else None
        if selected_loss is not None:
            running_best = min(running_best, selected_loss)
        selected.append(rel_improvement(baseline, selected_loss) or 0.0)
        best.append(rel_improvement(baseline, running_best) or 0.0)
    return list(range(len(best))), selected, best


def cost_to_tau(run: dict[str, Any]) -> tuple[float, float]:
    eval_path = Path(run["run_dir"]) / "evaluations.jsonl"
    if not eval_path.exists():
        return math.nan, math.nan
    records = [json.loads(raw) for raw in eval_path.read_text(encoding="utf-8").splitlines() if raw.strip()]
    if not records:
        return math.nan, math.nan
    tau = run.get("tau_step")
    cutoff = int(tau) if tau is not None else len(records)
    cutoff = min(max(cutoff, 1), len(records))
    selected = records[:cutoff]
    wall = sum(float(record.get("step_wall_seconds") or 0.0) for record in selected)
    tokens = sum(float(record.get("total_tokens") or 0.0) for record in selected)
    return wall, tokens


def run_token_resources(run: dict[str, Any]) -> tuple[float, float]:
    eval_path = Path(run["run_dir"]) / "evaluations.jsonl"
    if not eval_path.exists():
        return math.nan, math.nan
    total = 0.0
    output = 0.0
    seen = False
    for raw in eval_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        record = json.loads(raw)
        total += float(record.get("total_tokens") or 0.0)
        output += float(record.get("output_tokens") or 0.0)
        seen = True
    return (total, output) if seen else (math.nan, math.nan)


def occupancy_proxy(run: dict[str, Any]) -> float:
    steps = max(int(run.get("steps_completed") or 0), 1)
    tau = run.get("tau_step")
    if tau is None:
        return 0.0
    return (steps - max(int(tau), 0)) / steps


def threshold_stats(rows: list[dict[str, Any]], thresholds: list[float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overall: list[dict[str, Any]] = []
    by_worker: list[dict[str, Any]] = []

    def summarize(cell: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
        entry = 0
        taus: list[int] = []
        selected_occ: list[float] = []
        best_occ: list[float] = []
        for run in cell:
            _, selected, best = trajectory(run)
            if not best:
                selected = [float(run["relative_improvement"])]
                best = [float(run["relative_improvement"])]
            hit_steps = [idx + 1 for idx, value in enumerate(best[:20]) if value >= threshold]
            if hit_steps:
                entry += 1
                taus.append(hit_steps[0])
            selected_occ.append(sum(value >= threshold for value in selected[:20]) / max(len(selected[:20]), 1))
            best_occ.append(sum(value >= threshold for value in best[:20]) / max(len(best[:20]), 1))
        return {
            "threshold": threshold,
            "attempt_count": len(cell),
            "entry_success_prob": entry / len(cell) if cell else math.nan,
            "mean_tau": float(np.mean(taus)) if taus else None,
            "mean_selected_threshold_occupancy": float(np.mean(selected_occ)) if selected_occ else math.nan,
            "mean_best_threshold_hit_count": float(np.mean(best_occ)) * 20.0 if best_occ else math.nan,
        }

    for threshold in thresholds:
        overall.append(summarize(rows, threshold))
        for worker in WORKER_ORDER:
            row = summarize([item for item in rows if item["worker"] == worker], threshold)
            row["model_alias"] = worker
            by_worker.append(row)
    return overall, by_worker


def pilot_cell_metrics(pilot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        for worker in WORKER_ORDER:
            cell = [row for row in pilot if row["mode"] == mode and row["worker"] == worker]
            if not cell:
                continue
            costs = [cost_to_tau(row) for row in cell]
            wall = [value[0] for value in costs if math.isfinite(value[0]) and value[0] > 0.0]
            tokens = [value[1] for value in costs if math.isfinite(value[1]) and value[1] > 0.0]
            success_prob = sum(row["success"] for row in cell) / len(cell)
            p_for_log = max(success_prob, 0.5 / len(cell))
            mean_wall = float(np.mean(wall)) if wall else math.nan
            rows.append(
                {
                    "mode": mode,
                    "worker": worker,
                    "n": len(cell),
                    "success_prob": success_prob,
                    "occupancy": float(np.mean([occupancy_proxy(row) for row in cell])),
                    "mean_tau": float(np.mean([row["tau_step"] for row in cell if row["tau_step"] is not None]))
                    if any(row["tau_step"] is not None for row in cell)
                    else math.nan,
                    "mean_wall_to_tau": mean_wall,
                    "mean_tokens_to_tau": float(np.mean(tokens)) if tokens else math.nan,
                    "log_effort": math.log(mean_wall) - math.log(p_for_log) if math.isfinite(mean_wall) and mean_wall > 0.0 else math.nan,
                }
            )
    return rows


def matrix_for(rows: list[dict[str, Any]], value_fn) -> tuple[np.ndarray, list[list[str]]]:
    data = np.full((len(WORKER_ORDER), len(MODE_ORDER)), np.nan)
    ann = [["" for _ in MODE_ORDER] for _ in WORKER_ORDER]
    for i, worker in enumerate(WORKER_ORDER):
        for j, mode in enumerate(MODE_ORDER):
            cell = [row for row in rows if row["worker"] == worker and row["mode"] == mode]
            if not cell:
                ann[i][j] = "pending"
                continue
            value = value_fn(cell)
            data[i, j] = value
            ann[i][j] = f"{value:.2f}\nn={len(cell)}"
    return data, ann


def draw_heatmap(data: np.ndarray, annotations: list[list[str]], title: str, name: str, *, cmap: str = "Blues", vmin: float = 0.0, vmax: float = 1.0) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    masked = np.ma.masked_invalid(data)
    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad("#f0f0f0")
    im = ax.imshow(masked, vmin=vmin, vmax=vmax, cmap=cmap_obj, aspect="auto")
    ax.set_xticks(range(len(MODE_LABELS)))
    ax.set_xticklabels(MODE_LABELS)
    ax.set_yticks(range(len(WORKER_LABELS)))
    ax.set_yticklabels(WORKER_LABELS)
    ax.set_title(title)
    for i in range(len(WORKER_ORDER)):
        for j in range(len(MODE_ORDER)):
            ax.text(j, i, annotations[i][j], ha="center", va="center", fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    save(fig, name)


def plot_threshold_sensitivity(rows: list[dict[str, Any]]) -> None:
    thresholds = [0.01, 0.02, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
    overall, _ = threshold_stats(rows, thresholds)
    overall = sorted(overall, key=lambda row: row["threshold"])
    x = [row["threshold"] for row in overall]
    succ = [row["entry_success_prob"] for row in overall]
    tau = [row["mean_tau"] for row in overall]
    occ = [row["mean_selected_threshold_occupancy"] for row in overall]
    best_occ = [row["mean_best_threshold_hit_count"] / 20.0 for row in overall]

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.7))
    axes[0].plot(x, succ, marker="o", linewidth=2.2, color="#2a6fdb")
    axes[0].set_ylim(0.84, 1.02)
    axes[0].set_ylabel("entry success probability")
    axes[0].set_xlabel("threshold delta")
    axes[0].set_title("Entry probability")
    axes[1].plot(x, tau, marker="s", linewidth=2.2, color="#444444")
    axes[1].set_ylabel("mean first-hit step")
    axes[1].set_xlabel("threshold delta")
    axes[1].set_title("Time to threshold")
    axes[2].plot(x, occ, marker="^", linewidth=2.2, color="#e38d2c", label="selected")
    axes[2].plot(x, best_occ, marker="d", linestyle="--", linewidth=1.8, color="#8a5a00", label="best-so-far")
    axes[2].set_ylim(0.48, 0.96)
    axes[2].set_ylabel("fraction of H=20 steps")
    axes[2].set_xlabel("threshold delta")
    axes[2].set_title("Threshold occupancy")
    axes[2].legend()
    for ax in axes:
        ax.axvline(0.05, linestyle=":", color="#cc0000", linewidth=1.4)
    fig.suptitle(f"Threshold sensitivity, balanced three-worker pooled support (n={len(rows)})", y=1.04)
    save(fig, "01_threshold_sensitivity_current_pilot")

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.7))
    axes[0].plot(x, succ, marker="o", linewidth=2.2, color="#2a6fdb")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].set_ylabel("entry success probability")
    axes[0].set_xlabel("relative improvement threshold delta")
    axes[0].set_title("Entry probability")
    axes[1].plot(x, tau, marker="s", linewidth=2.2, color="#444444")
    axes[1].set_ylabel("mean first-hit step")
    axes[1].set_xlabel("relative improvement threshold delta")
    axes[1].set_title("Time to threshold")
    axes[2].plot(x, occ, marker="^", linewidth=2.2, color="#e38d2c", label="selected")
    axes[2].plot(x, best_occ, marker="d", linestyle="--", linewidth=1.8, color="#8a5a00", label="best-so-far")
    axes[2].set_ylim(-0.03, 0.96)
    axes[2].set_ylabel("fraction of H=20 steps")
    axes[2].set_xlabel("relative improvement threshold delta")
    axes[2].set_title("Threshold occupancy")
    axes[2].legend()
    for ax in axes:
        ax.axvline(0.05, linestyle=":", color="#cc0000", linewidth=1.4, label="delta=0.05")
        ax.axvline(max(x), linestyle="--", color="#666666", linewidth=1.1, label=f"last >0: {max(x):.2f}")
    fig.suptitle(f"Extended threshold sensitivity, balanced three-worker pooled support (n={len(rows)})", y=1.04)
    save(fig, "01b_threshold_sensitivity_extended_current_pilot")


def plot_threshold_sensitivity_by_model(rows: list[dict[str, Any]]) -> None:
    thresholds = [0.01, 0.02, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]
    _, by_model = threshold_stats(rows, thresholds)
    if not by_model:
        return
    colors = WORKER_COLORS
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 3.9))
    for worker in WORKER_ORDER:
        worker_rows = sorted([row for row in by_model if normalize_worker(row["model_alias"]) == worker], key=lambda row: row["threshold"])
        if not worker_rows:
            continue
        x = [row["threshold"] for row in worker_rows]
        label = f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} (n={worker_rows[0]['attempt_count']})"
        axes[0].plot(x, [row["entry_success_prob"] for row in worker_rows], marker="o", linewidth=2.0, color=colors[worker], label=label)
        axes[1].plot(x, [np.nan if row["mean_tau"] is None else row["mean_tau"] for row in worker_rows], marker="s", linewidth=2.0, color=colors[worker])
        axes[2].plot(x, [row["mean_selected_threshold_occupancy"] for row in worker_rows], marker="^", linewidth=2.0, color=colors[worker])
    for ax in axes:
        ax.axvline(0.05, linestyle=":", color="#cc0000", linewidth=1.3)
        ax.set_xlabel("threshold delta")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].set_ylabel("entry success probability")
    axes[0].set_title("Entry probability by worker")
    axes[1].set_ylabel("mean first-hit step")
    axes[1].set_title("Time to threshold by worker")
    axes[2].set_ylim(-0.03, 1.03)
    axes[2].set_ylabel("selected occupancy")
    axes[2].set_title("Occupancy by worker")
    axes[0].legend(fontsize=7, loc="lower left")
    fig.suptitle(f"Extended threshold sensitivity by worker, balanced n=34 support (n={len(rows)})", y=1.04)
    save(fig, "01b_threshold_sensitivity_by_worker")


def plot_improvement_distribution(pilot: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.3, 4.0))
    colors = WORKER_COLORS
    rng = np.random.default_rng(20260506)
    for i, worker in enumerate(WORKER_ORDER):
        rows = [row for row in pilot if row["worker"] == worker]
        if not rows:
            continue
        y = np.full(len(rows), i, dtype=float) + rng.uniform(-0.12, 0.12, size=len(rows))
        x = [row["relative_improvement"] for row in rows]
        axes[0].scatter(x, y, s=28, alpha=0.75, color=colors[worker], label=f"{WORKER_LABELS[i]} (n={len(rows)})")
        axes[0].vlines(float(np.median(x)), i - 0.28, i + 0.28, color=colors[worker], linewidth=3.0)
        sorted_x = np.sort(np.array(x))
        survival = 1.0 - np.arange(len(sorted_x)) / len(sorted_x)
        axes[1].step(sorted_x, survival, where="post", color=colors[worker], linewidth=2.1, label=f"{WORKER_LABELS[i]} (n={len(rows)})")
    for threshold in [0.05, 0.10, 0.15, 0.20, 0.30]:
        axes[0].axvline(threshold, color="#777777" if threshold != 0.05 else "#cc0000", linestyle=":" if threshold == 0.05 else "--", linewidth=1.0)
        axes[1].axvline(threshold, color="#777777" if threshold != 0.05 else "#cc0000", linestyle=":" if threshold == 0.05 else "--", linewidth=1.0)
    axes[0].set_yticks(range(len(WORKER_LABELS)))
    axes[0].set_yticklabels(WORKER_LABELS)
    axes[0].set_xlabel("best visible relative improvement")
    axes[0].set_title("Run-level improvement dots; thick mark = median")
    axes[1].set_xlabel("threshold delta")
    axes[1].set_ylabel("P(best improvement >= delta)")
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].set_title("Empirical survival curve")
    axes[1].legend(fontsize=7)
    fig.suptitle("Why threshold choice matters: pooled run-level improvement distribution", y=1.04)
    save(fig, "01c_improvement_distribution_by_worker")


def plot_success_tau_occupancy(pilot: list[dict[str, Any]]) -> None:
    success, ann = matrix_for(pilot, lambda cell: sum(row["success"] for row in cell) / len(cell))
    draw_heatmap(success, ann, "Pilot entry success at delta=0.05", "02_success_heatmap_pilot", cmap="Blues")

    occ, occ_ann = matrix_for(pilot, lambda cell: sum((row["steps_completed"] - max(int(row["tau_step"] or row["steps_completed"] + 1), 0)) / max(row["steps_completed"], 1) if row["tau_step"] is not None else 0.0 for row in cell) / len(cell))
    draw_heatmap(occ, occ_ann, "Pilot threshold occupancy proxy", "03_occupancy_heatmap_pilot", cmap="Oranges")

    fig, ax = plt.subplots(figsize=(11.2, 4.9))
    colors = WORKER_COLORS
    offsets = dict(zip(WORKER_ORDER, np.linspace(-0.24, 0.24, len(WORKER_ORDER))))
    positions: list[float] = []
    values: list[list[int]] = []
    cell_workers: list[str] = []
    rng = np.random.default_rng(20260506)
    for mode in MODE_ORDER:
        mode_index = MODE_ORDER.index(mode)
        for worker in WORKER_ORDER:
            xs = [row["tau_step"] for row in pilot if row["mode"] == mode and row["worker"] == worker and row["tau_step"] is not None]
            if not xs:
                continue
            values.append(xs)
            positions.append(mode_index + offsets[worker])
            cell_workers.append(worker)

    if not values:
        return

    parts = ax.violinplot(
        values,
        positions=positions,
        widths=0.23,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for body, worker in zip(parts["bodies"], cell_workers):
        body.set_facecolor(colors[worker])
        body.set_edgecolor("#2b2b2b")
        body.set_linewidth(0.8)
        body.set_alpha(0.28)

    for p, xs, worker in zip(positions, values, cell_workers):
        arr = np.asarray(xs, dtype=float)
        q1, med, q3 = np.percentile(arr, [25, 50, 75])
        ax.vlines(p, q1, q3, color=colors[worker], linewidth=5.5, alpha=0.9, zorder=3)
        ax.scatter([p], [med], marker="D", s=30, color="#ffffff", edgecolor=colors[worker], linewidth=1.5, zorder=4)
        jitter = rng.uniform(-0.055, 0.055, size=len(xs))
        ax.scatter(
            p + jitter,
            arr,
            s=24,
            alpha=0.72,
            color=colors[worker],
            edgecolor="#ffffff",
            linewidth=0.45,
            zorder=5,
        )
        ax.text(p, 20.75, f"n={len(xs)}", ha="center", va="top", fontsize=7, color="#555555")

    for boundary in [0.5, 1.5]:
        ax.axvline(boundary, color="#d2d2d2", linewidth=1.0, linestyle="--", zorder=0)
    ax.axhspan(0.5, 4.0, color="#2a6fdb", alpha=0.045, zorder=0)
    ax.set_xlim(-0.65, len(MODE_ORDER) - 0.35)
    ax.set_ylim(0.5, 21.0)
    ax.set_xticks(range(len(MODE_ORDER)))
    ax.set_xticklabels(MODE_LABELS)
    ax.set_ylabel("first-hit step $\\tau_{0.05}$")
    ax.set_xlabel("canonical AutoResearch mode")
    ax.set_title("Pooled time-to-success distribution", pad=12)
    handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", markersize=7, markerfacecolor=colors[worker], markeredgecolor="#ffffff", label=WORKER_LABELS[i])
        for i, worker in enumerate(WORKER_ORDER)
    ]
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=True, framealpha=0.95, title="Worker")
    save(fig, "04_tau_distribution_pilot")


def plot_trajectories(pilot: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, len(MODE_ORDER), figsize=(13.5, 3.8), sharey=True)
    colors = WORKER_COLORS
    for ax, mode in zip(axes, MODE_ORDER):
        for worker in WORKER_ORDER:
            runs = [row for row in pilot if row["mode"] == mode and row["worker"] == worker]
            traces = []
            for run in runs:
                _, _, best = trajectory(run)
                if best:
                    traces.append(best[:20])
            if not traces:
                continue
            max_len = max(len(item) for item in traces)
            arr = np.full((len(traces), max_len), np.nan)
            for i, item in enumerate(traces):
                arr[i, : len(item)] = item
            mean = np.nanmean(arr, axis=0)
            lo = np.nanpercentile(arr, 25, axis=0)
            hi = np.nanpercentile(arr, 75, axis=0)
            x = np.arange(len(mean))
            ax.plot(x, mean, label=f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} (n={len(traces)})", color=colors[worker], linewidth=2.0)
            ax.fill_between(x, lo, hi, color=colors[worker], alpha=0.15)
        ax.axhline(THRESHOLD, color="#cc0000", linestyle=":", linewidth=1.3)
        ax.set_title(MODE_LABELS[MODE_ORDER.index(mode)])
        ax.set_xlabel("step")
    axes[0].set_ylabel("best visible relative improvement")
    axes[-1].legend(loc="lower right", fontsize=7)
    fig.suptitle("Pooled best-so-far improvement trajectories", y=1.03)
    save(fig, "05_relative_improvement_trajectories_pilot")


def plot_trajectory_spaghetti(pilot: list[dict[str, Any]]) -> None:
    colors = WORKER_COLORS
    fig, axes = plt.subplots(1, len(MODE_ORDER), figsize=(13.8, 3.9), sharey=True)
    for ax, mode in zip(axes, MODE_ORDER):
        for worker in WORKER_ORDER:
            traces = []
            for run in [row for row in pilot if row["mode"] == mode and row["worker"] == worker]:
                x, _, best = trajectory(run)
                if not best:
                    continue
                traces.append(best[:20])
                ax.plot(x[:20], best[:20], color=colors[worker], alpha=0.13, linewidth=0.9)
                ax.scatter(x[:20], best[:20], color=colors[worker], alpha=0.18, s=8)
            if traces:
                max_len = max(len(item) for item in traces)
                arr = np.full((len(traces), max_len), np.nan)
                for i, item in enumerate(traces):
                    arr[i, : len(item)] = item
                mean = np.nanmean(arr, axis=0)
                ax.plot(np.arange(len(mean)), mean, color=colors[worker], linewidth=2.7, label=f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} mean (n={len(traces)})")
        ax.axhline(THRESHOLD, color="#cc0000", linestyle=":", linewidth=1.3)
        ax.set_title(MODE_LABELS[MODE_ORDER.index(mode)])
        ax.set_xlabel("step")
    axes[0].set_ylabel("best visible relative improvement")
    axes[-1].legend(loc="lower right", fontsize=7)
    fig.suptitle("Pooled trajectories: individual runs plus worker mean", y=1.04)
    save(fig, "05b_relative_improvement_spaghetti_with_mean")


def plot_throughput() -> None:
    path = CAMPAIGN_ROOT / "accounting" / "throughput_modes" / "throughput_report.json"
    if not path.exists():
        return
    data = load_json(path)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for mode in MODE_ORDER:
        rows = sorted([row for row in data["summary"] if row["mode"] == mode], key=lambda row: row["max_train_steps"])
        if not rows:
            continue
        label = MODE_LABELS[MODE_ORDER.index(mode)]
        axes[0].plot([row["max_train_steps"] for row in rows], [row["median_training_seconds"] for row in rows], marker="o", linewidth=2.0, label=label)
        axes[1].plot([row["max_train_steps"] for row in rows], [row["median_steps_per_second"] for row in rows], marker="s", linewidth=2.0, label=label)
    axes[0].set_xlabel("checker train steps")
    axes[0].set_ylabel("median training seconds")
    axes[0].set_title("Checker cost")
    axes[1].set_xlabel("checker train steps")
    axes[1].set_ylabel("median steps / second")
    axes[1].set_title("CPU throughput")
    for ax in axes:
        ax.legend()
    save(fig, "06_throughput_calibration")


def z_records_for_runs(rows: list[dict[str, Any]]) -> list[Any]:
    selected_dirs = {Path(row["run_dir"]).resolve() for row in rows}
    records = load_records([
        CAMPAIGN_ROOT / "runs" / "worker_pilot",
        CAMPAIGN_ROOT / "runs" / "worker_confirmation",
    ])
    return [record for record in records if record.run_dir.resolve() in selected_dirs]


def plot_z_ablation(rows: list[dict[str, Any]]) -> None:
    records = z_records_for_runs(rows)
    if not records:
        return
    names = ["budget_only", "probe_only", "probe_plus_budget", "leaky_current"]
    labels = ["budget", "probe", "probe+budget", "leaky current"]
    results = {name: evaluate_feature_set(records, FEATURE_SETS[name]) for name in names}
    vals = [results[name]["macro_accuracy"] for name in names]
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    bars = ax.bar(range(len(names)), vals, color=["#999999", "#4c78a8", "#72b7b2", "#f58518"])
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("leave-one-out macro accuracy")
    ax.set_title(f"Z-signal mode prediction ablation (balanced n={len(records)})")
    for bar, value in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.2f}", ha="center", fontsize=8)
    save(fig, "07_z_signal_ablation")


def plot_z_ablation_by_worker(rows: list[dict[str, Any]]) -> None:
    records = z_records_for_runs(rows)
    if not records:
        return
    names = ["budget_only", "probe_only", "probe_plus_budget", "leaky_current"]
    labels = ["budget", "probe", "probe+budget", "leaky"]
    by_worker: dict[str, list[Any]] = defaultdict(list)
    for record in records:
        manifest = load_json(record.run_dir / "run_manifest.json")
        by_worker[normalize_worker(manifest.get("model_alias") or "unknown")].append(record)

    fig, ax = plt.subplots(figsize=(8.8, 4.0))
    x = np.arange(len(names))
    width = 0.23
    colors = WORKER_COLORS
    offsets = np.linspace(-width, width, len(WORKER_ORDER))
    for offset, worker in zip(offsets, WORKER_ORDER):
        worker_records = by_worker.get(worker, [])
        if not worker_records:
            continue
        vals = [evaluate_feature_set(worker_records, FEATURE_SETS[name])["macro_accuracy"] for name in names]
        bars = ax.bar(
            x + offset,
            vals,
            width=width,
            color=colors[worker],
            label=f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} (n={len(worker_records)})",
        )
        for bar, value in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.018, f"{value:.2f}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("leave-one-out macro accuracy")
    ax.set_title("Z-signal mode prediction ablation by worker, balanced n=34 support")
    ax.legend(fontsize=7, loc="upper left")
    save(fig, "07b_z_signal_ablation_by_worker")


def plot_deployment_frontier() -> None:
    path = CAMPAIGN_ROOT / "accounting" / "threeworker_n34_final_analysis.json"
    if not path.exists():
        path = CAMPAIGN_ROOT / "accounting" / "threeworker_final_analysis.json"
    if not path.exists():
        return
    rows = load_json(path).get("frontier", [])
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    markers = dict(zip(MODE_ORDER, ["o", "s", "^"]))
    for row in rows:
        worker = normalize_worker(row["worker"])
        mode = row["mode"]
        x = float(row["log_effort_objective"])
        y = float(row["mean_final_relative_improvement"])
        ax.scatter(
            x,
            y,
            s=85,
            color=WORKER_COLORS.get(worker, "#777777"),
            marker=markers.get(mode, "o"),
            edgecolor="black",
            linewidth=0.5,
        )
        ax.text(
            x,
            y + 0.006,
            f"{mode.replace('_', ' ')}\n{worker.replace('gpt-', '')}",
            fontsize=7,
            ha="center",
        )
    ax.set_xlabel("log-effort objective (lower is better)")
    ax.set_ylabel("mean final relative improvement")
    ax.set_title("Deployment frontier snapshot (balanced n=34 per cell)")
    save(fig, "08_deployment_frontier_snapshot")

def plot_router_snapshot() -> None:
    path = CAMPAIGN_ROOT / "router" / "router_decisions_threeworker_z0_z3_controls.jsonl"
    if not path.exists() or path.stat().st_size == 0:
        return
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    completed = [row for row in rows if row.get("router_output")]
    if not completed:
        return
    counts = Counter(
        (
            row["signal_level"],
            row["negative_control"],
            normalize_worker(row["router_output"].get("selected_agent_model") or row["router_output"].get("selected_worker")),
        )
        for row in completed
    )
    signal_levels = ["Z0", "Z1", "Z2", "Z3"]
    controls = ["none", "shuffle_probe", "wrong_mode_probe", "synthetic_noise"]

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.2), sharey=True)
    for ax, control in zip(axes, ["none", "wrong_mode_probe"]):
        bottom = np.zeros(len(signal_levels))
        for worker in WORKER_ORDER:
            values = []
            for signal in signal_levels:
                total = sum(counts[(signal, control, w)] for w in WORKER_ORDER)
                values.append(counts[(signal, control, worker)] / total if total else 0.0)
            ax.bar(signal_levels, values, bottom=bottom, label=WORKER_LABELS[WORKER_ORDER.index(worker)])
            bottom += np.array(values)
        ax.set_title(f"Router selected worker, control={control}")
        ax.set_ylabel("selection share")
        ax.set_ylim(0, 1.0)
    axes[1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.suptitle(f"Three-worker router decision snapshot ({len(completed)}/480 records complete)", y=1.03)
    save(fig, "09_router_selection_snapshot")

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    record_counts = Counter((row["signal_level"], row["negative_control"]) for row in completed)
    matrix = np.zeros((len(controls), len(signal_levels)))
    for i, control in enumerate(controls):
        for j, signal in enumerate(signal_levels):
            matrix[i, j] = record_counts[(signal, control)]
    im = ax.imshow(matrix, cmap="Greens", aspect="auto")
    ax.set_xticks(range(len(signal_levels)))
    ax.set_xticklabels(signal_levels)
    ax.set_yticks(range(len(controls)))
    ax.set_yticklabels(controls)
    ax.set_title("Router record completion")
    for i in range(len(controls)):
        for j in range(len(signal_levels)):
            ax.text(j, i, f"{int(matrix[i,j])}", ha="center", va="center", fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    save(fig, "10_router_record_completion")


def plot_confirmation_progress(confirmation: list[dict[str, Any]]) -> None:
    if not confirmation:
        return
    counts = Counter((row["mode"], row["worker"]) for row in confirmation)
    succ = Counter((row["mode"], row["worker"]) for row in confirmation if row["success"])
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    labels = []
    complete = []
    success = []
    for mode in MODE_ORDER:
        for worker in WORKER_ORDER:
            labels.append(f"{MODE_LABELS[MODE_ORDER.index(mode)]}\n{worker.replace('gpt-', '')}")
            complete.append(counts[(mode, worker)])
            success.append(succ[(mode, worker)])
    x = np.arange(len(labels))
    ax.bar(x, complete, color="#d6d6d6", label="completed")
    ax.bar(x, success, color="#2a6fdb", label="success")
    ax.axhline(30, color="#444444", linestyle=":", linewidth=1.2, label="target per cell")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("runs")
    ax.set_title("Confirmation progress snapshot")
    ax.legend()
    save(fig, "11_confirmation_progress")


def plot_worker_cost_quality(pilot: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for run in pilot:
        total_tokens, output_tokens = run_token_resources(run)
        if not math.isfinite(total_tokens) or not math.isfinite(output_tokens):
            continue
        rows.append({**run, "total_tokens": total_tokens, "output_tokens": output_tokens})
    if not rows:
        return
    colors = WORKER_COLORS
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.2))
    panels = [
        ("elapsed_wall_seconds", 60.0, "wall time per run (minutes)", "Quality vs wall-clock"),
        ("total_tokens", 1_000_000.0, "total tokens per run (millions; cached included)", "Quality vs token accounting"),
        ("output_tokens", 1_000.0, "output tokens per run (thousands)", "Quality vs generation size"),
    ]
    for ax, (key, scale, xlabel, title) in zip(axes, panels):
        for worker in WORKER_ORDER:
            cell = [row for row in rows if row["worker"] == worker]
            if not cell:
                continue
            xs = np.array([float(row[key]) / scale for row in cell], dtype=float)
            ys = np.array([float(row["relative_improvement"]) for row in cell], dtype=float)
            ax.scatter(xs, ys, s=34, alpha=0.62, color=colors[worker], label=f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} (n={len(cell)})")
            ax.scatter(float(np.median(xs)), float(np.median(ys)), s=120, marker="D", color=colors[worker], edgecolor="black", linewidth=1.0, zorder=5)
        ax.axhline(THRESHOLD, color="red", linestyle=":", linewidth=1.2)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("best relative improvement")
        ax.set_title(title)
    axes[0].legend(loc="lower right", fontsize=7)
    fig.suptitle("Worker cost/quality diagnostics, balanced n=34 support", y=1.04)
    save(fig, "12_worker_cost_quality_diagnostics")


def plot_first_hit_cdf(pilot: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(1, len(MODE_ORDER), figsize=(13.4, 3.9), sharey=True)
    colors = WORKER_COLORS
    horizon = max([row["steps_completed"] for row in pilot if row.get("steps_completed")] or [20])
    steps = np.arange(1, horizon + 1)
    for ax, mode in zip(axes, MODE_ORDER):
        for worker in WORKER_ORDER:
            cell = [row for row in pilot if row["mode"] == mode and row["worker"] == worker]
            if not cell:
                continue
            taus = [row["tau_step"] for row in cell]
            cdf = [sum(tau is not None and tau <= step for tau in taus) / len(taus) for step in steps]
            linestyle = "-" if len(cell) >= 5 else ":"
            ax.step(steps, cdf, where="post", linewidth=2.4, linestyle=linestyle, color=colors[worker], label=f"{WORKER_LABELS[WORKER_ORDER.index(worker)]} (n={len(cell)})")
        ax.set_title(MODE_LABELS[MODE_ORDER.index(mode)])
        ax.set_xlabel("edit-verify step h")
        ax.set_xlim(1, horizon)
        ax.set_ylim(-0.03, 1.03)
        ax.axhline(0.5, color="#999999", linewidth=0.8, linestyle=":")
    axes[0].set_ylabel("P($\\tau_{0.05} \\leq h$)")
    handles = [
        plt.Line2D([0], [0], color=colors[worker], linewidth=2.8, label=WORKER_LABELS[i])
        for i, worker in enumerate(WORKER_ORDER)
    ]
    axes[-1].legend(handles=handles, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=True, title="Worker")
    fig.suptitle("First-hit cumulative success curves", y=1.04)
    save(fig, "14_first_hit_cdf_by_mode")


def plot_entry_occupancy_scatter(pilot: list[dict[str, Any]]) -> None:
    rows = pilot_cell_metrics(pilot)
    if not rows:
        return
    colors = WORKER_COLORS
    markers = dict(zip(MODE_ORDER, ["o", "s", "^"]))
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    for row in rows:
        worker = row["worker"]
        mode = row["mode"]
        partial = row["n"] < 5
        ax.scatter(
            row["success_prob"],
            row["occupancy"],
            s=78 + 8 * row["n"],
            color=colors[worker],
            marker=markers[mode],
            alpha=0.42 if partial else 0.88,
            edgecolor="#222222",
            linewidth=0.8,
        )
        if partial:
            ax.annotate(f"n={row['n']}", (row["success_prob"], row["occupancy"]), xytext=(5, 5), textcoords="offset points", fontsize=7, color="#555555")
    ax.axvline(0.95, color="#888888", linewidth=1.0, linestyle=":")
    ax.axhline(float(np.nanmedian([row["occupancy"] for row in rows])), color="#888888", linewidth=1.0, linestyle=":")
    ax.set_xlim(0.82, 1.015)
    ax.set_ylim(0.46, 0.97)
    ax.set_xlabel("entry success probability at $\\delta=0.05$")
    ax.set_ylabel("threshold occupancy proxy")
    ax.set_title("Entry success versus persistence")
    worker_handles = [
        plt.Line2D([0], [0], marker="o", linestyle="", markersize=7, markerfacecolor=colors[worker], markeredgecolor="#222222", label=WORKER_LABELS[i])
        for i, worker in enumerate(WORKER_ORDER)
    ]
    mode_handles = [
        plt.Line2D([0], [0], marker=markers[mode], linestyle="", markersize=7, markerfacecolor="#ffffff", markeredgecolor="#222222", label=MODE_LABELS[i])
        for i, mode in enumerate(MODE_ORDER)
    ]
    leg1 = ax.legend(handles=worker_handles, loc="lower left", frameon=True, title="Worker")
    ax.add_artist(leg1)
    ax.legend(handles=mode_handles, loc="upper left", frameon=True, title="Mode")
    save(fig, "15_entry_vs_occupancy")


def plot_cost_adjusted_frontier_by_mode(pilot: list[dict[str, Any]]) -> None:
    rows = pilot_cell_metrics(pilot)
    if not rows:
        return
    colors = WORKER_COLORS
    fig, axes = plt.subplots(1, len(MODE_ORDER), figsize=(13.0, 4.1), sharey=True)
    for ax, mode in zip(axes, MODE_ORDER):
        cell_rows = [row for row in rows if row["mode"] == mode and math.isfinite(row["log_effort"])]
        if not cell_rows:
            ax.set_visible(False)
            continue
        best = min(row["log_effort"] for row in cell_rows)
        x = np.arange(len(WORKER_ORDER))
        values = []
        labels = []
        bar_colors = []
        hatches = []
        for worker in WORKER_ORDER:
            row = next((item for item in cell_rows if item["worker"] == worker), None)
            values.append(np.nan if row is None else row["log_effort"] - best)
            labels.append("pending" if row is None else f"n={row['n']}")
            bar_colors.append(colors[worker])
            hatches.append("//" if row is not None and row["n"] < 5 else "")
        bars = ax.bar(x, values, color=bar_colors, alpha=0.86, edgecolor="#222222", linewidth=0.7)
        for bar, hatch in zip(bars, hatches):
            bar.set_hatch(hatch)
        for i, (value, label) in enumerate(zip(values, labels)):
            if math.isfinite(value):
                ax.text(i, value + 0.025, label, ha="center", va="bottom", fontsize=7)
                if abs(value) < 1e-9:
                    ax.scatter(i, 0.0, marker="D", s=32, color="#ffffff", edgecolor="#222222", linewidth=1.0, zorder=5)
        ax.axhline(0.0, color="#222222", linewidth=1.0)
        ax.set_xticks(x)
        ax.set_xticklabels([label.replace("GPT-", "") for label in WORKER_LABELS], rotation=25, ha="right")
        ax.set_title(MODE_LABELS[MODE_ORDER.index(mode)])
        ax.set_xlabel("worker")
    axes[0].set_ylabel("excess log-effort vs mode frontier\nlower is better")
    fig.suptitle("Cost-adjusted first-hit frontier by mode", y=1.04)
    save(fig, "16_cost_adjusted_frontier_by_mode")


def plot_cost_to_tau(pilot: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    for run in pilot:
        wall, tokens = cost_to_tau(run)
        if math.isfinite(wall) and math.isfinite(tokens):
            rows.append({**run, "wall_to_tau": wall, "tokens_to_tau": tokens})
    if not rows:
        return
    colors = WORKER_COLORS
    offsets = dict(zip(WORKER_ORDER, np.linspace(-0.24, 0.24, len(WORKER_ORDER))))
    fig, axes = plt.subplots(2, len(MODE_ORDER), figsize=(13.5, 6.2), sharex=True)
    rng = np.random.default_rng(20260506)
    for col, mode in enumerate(MODE_ORDER):
        for worker in WORKER_ORDER:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            if not cell:
                continue
            x0 = offsets[worker]
            wall_vals = np.array([row["wall_to_tau"] / 60.0 for row in cell], dtype=float)
            token_vals = np.array([row["tokens_to_tau"] / 1000.0 for row in cell], dtype=float)
            for ax, vals in [(axes[0, col], wall_vals), (axes[1, col], token_vals)]:
                x = np.full(len(vals), x0) + rng.uniform(-0.045, 0.045, len(vals))
                ax.scatter(x, vals, s=24, alpha=0.72, color=colors[worker], edgecolor="#ffffff", linewidth=0.4)
                ax.hlines(float(np.median(vals)), x0 - 0.075, x0 + 0.075, color=colors[worker], linewidth=3.0)
        axes[0, col].set_title(MODE_LABELS[col])
        for row_ax in axes[:, col]:
            row_ax.set_xlim(-0.55, 0.55)
            row_ax.set_xticks([offsets[worker] for worker in WORKER_ORDER])
            row_ax.set_xticklabels([label.replace("GPT-", "") for label in WORKER_LABELS], rotation=25, ha="right")
            row_ax.grid(axis="x", visible=False)
        axes[1, col].set_yscale("log")
    axes[0, 0].set_ylabel("worker wall minutes\nto $\\tau \\wedge H$")
    axes[1, 0].set_ylabel("worker tokens, thousands\nto $\\tau \\wedge H$ (log)")
    fig.suptitle("Resource cost accumulated to first hit or horizon", y=1.02)
    save(fig, "17_cost_to_tau_by_mode_worker")


def write_index(generated: list[str]) -> None:
    lines = [
        "# Current Snapshot Figures",
        "",
        "Generated from the balanced three-worker pooled panel: 10 pilot + 24 holdout runs per mode/worker cell (n=34), using gpt_5_3_codex, gpt_5_4, and gpt_5_4_mini. Spark is excluded.",
        "",
    ]
    for name in generated:
        lines.append(f"- `{name}.png` / `{name}.pdf`")
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    pilot = load_runs(CAMPAIGN_ROOT / "runs" / "worker_pilot")
    confirmation = load_runs(CAMPAIGN_ROOT / "runs" / "worker_confirmation")
    pooled = pooled_pilot_holdout_panel(pilot + confirmation)
    generated = [
        "01_threshold_sensitivity_current_pilot",
        "01b_threshold_sensitivity_by_worker",
        "01b_threshold_sensitivity_extended_current_pilot",
        "01c_improvement_distribution_by_worker",
        "02_success_heatmap_pilot",
        "03_occupancy_heatmap_pilot",
        "04_tau_distribution_pilot",
        "05_relative_improvement_trajectories_pilot",
        "05b_relative_improvement_spaghetti_with_mean",
        "06_throughput_calibration",
        "07_z_signal_ablation",
        "07b_z_signal_ablation_by_worker",
        "08_deployment_frontier_snapshot",
        "09_router_selection_snapshot",
        "10_router_record_completion",
        "11_confirmation_progress",
        "12_worker_cost_quality_diagnostics",
        "14_first_hit_cdf_by_mode",
        "15_entry_vs_occupancy",
        "16_cost_adjusted_frontier_by_mode",
        "17_cost_to_tau_by_mode_worker",
        "threeworker_frozen_confirmation_frontier",
        "threeworker_deployment_frontier",
        "threeworker_threshold_sensitivity",
        "threeworker_router_selection_regret",
        "threeworker_router_paired_gain",
        "threeworker_negative_controls",
        "threeworker_crossover_applicability",
        "threeworker_improvement_distribution",
        "threeworker_tau_distribution",
        "threeworker_relative_improvement_trajectories",
        "threeworker_worker_cost_quality_diagnostics",
        "threeworker_cost_to_tau_by_mode_worker",
    ]
    plot_threshold_sensitivity(pooled)
    plot_threshold_sensitivity_by_model(pooled)
    plot_improvement_distribution(pooled)
    plot_success_tau_occupancy(pooled)
    plot_trajectories(pooled)
    plot_trajectory_spaghetti(pooled)
    plot_throughput()
    plot_z_ablation(pooled)
    plot_z_ablation_by_worker(pooled)
    plot_deployment_frontier()
    plot_router_snapshot()
    plot_confirmation_progress(confirmation)
    plot_worker_cost_quality(pooled)
    plot_first_hit_cdf(pooled)
    plot_entry_occupancy_scatter(pooled)
    plot_cost_adjusted_frontier_by_mode(pooled)
    plot_cost_to_tau(pooled)
    generated = [
        name
        for name in generated
        if (OUT_DIR / f"{name}.png").exists() and (OUT_DIR / f"{name}.pdf").exists()
    ]
    write_index(generated)
    support = Counter((row["mode"], row["worker"]) for row in pooled)
    print(json.dumps({"output_dir": str(OUT_DIR), "pooled_common_support": {f"{k[0]}/{k[1]}": v for k, v in sorted(support.items())}, "figures": generated}, indent=2))


if __name__ == "__main__":
    main()
