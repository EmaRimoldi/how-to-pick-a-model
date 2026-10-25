"""Frozen three-worker analysis for the AutoResearch CIFAR-10 paper experiments."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODES = ["mlp_flat", "cnn_compact", "resnet_micro"]
MODE_LABELS = {"cnn_compact": "CNN", "mlp_flat": "MLP", "resnet_micro": "ResNet"}
WORKERS = ["gpt_5_3_codex", "gpt_5_4", "gpt_5_4_mini"]
WORKER_LABELS = {
    "gpt_5_3_codex": "GPT-5.3 Codex",
    "gpt_5_4": "GPT-5.4",
    "gpt_5_4_mini": "GPT-5.4 Mini",
}
WORKER_SHORT = {"gpt_5_3_codex": "C", "gpt_5_4": "4", "gpt_5_4_mini": "m"}
WORKER_COLORS = {"gpt_5_3_codex": "#4C78A8", "gpt_5_4": "#F58518", "gpt_5_4_mini": "#54A24B"}
WORKER_TARGETS = {"gpt_5_3_codex": 35, "gpt_5_4": 35, "gpt_5_4_mini": 30}
PILOT_TARGETS = {"gpt_5_3_codex": 10, "gpt_5_4": 10, "gpt_5_4_mini": 10}
THRESHOLD = 0.05
THRESHOLD_GRID = [0.01, 0.02, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
MAIN_THRESHOLDS = [0.02, 0.05, 0.10, 0.20]


def fmean(values) -> float:
    xs = list(values)
    return sum(xs) / len(xs) if xs else math.nan


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rel_improvement(baseline: float, loss: float | None) -> float:
    if loss is None or not math.isfinite(loss) or not math.isfinite(baseline) or baseline <= 0:
        return 0.0
    return (baseline - loss) / baseline


def percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    if not xs:
        return math.nan
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def bootstrap_ci(values: list[float], samples: int = 2000, seed: int = 20260506) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "lo": None, "hi": None}
    rng = np.random.default_rng(seed)
    draws = rng.choice(np.array(values, dtype=float), size=(samples, len(values)), replace=True).mean(axis=1)
    return {
        "mean": float(np.mean(values)),
        "lo": float(np.quantile(draws, 0.025)),
        "hi": float(np.quantile(draws, 0.975)),
    }


def step_records(run_dir: Path) -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(run_dir.glob("steps/step_*/step_record.json"))]


def selected_final_loss(rows: list[dict[str, Any]], fallback: float | None) -> float | None:
    final = None
    for row in rows:
        selected = next((b for b in row.get("branches", []) if b.get("promoted_as_parent")), None)
        if selected and selected.get("correctness") and selected.get("latent_loss") is not None:
            final = safe_float(selected["latent_loss"])
    return final if final is not None else fallback


def selected_loss_by_step(rows: list[dict[str, Any]]) -> list[float | None]:
    values: list[float | None] = []
    for row in rows:
        selected = next((b for b in row.get("branches", []) if b.get("promoted_as_parent")), None)
        if selected and selected.get("correctness") and selected.get("latent_loss") is not None:
            values.append(safe_float(selected["latent_loss"]))
        else:
            values.append(None)
    return values


def best_visible_by_step(baseline: float, selected_losses: list[float | None]) -> list[float | None]:
    running = baseline if math.isfinite(baseline) and baseline > 0 else math.inf
    values: list[float | None] = []
    for loss in selected_losses:
        if loss is not None and math.isfinite(loss):
            running = min(running, loss)
        values.append(running if running != math.inf else None)
    return values


def first_hit_step(baseline: float, losses_by_step: list[float | None], threshold: float) -> int | None:
    for step, loss in enumerate(losses_by_step, start=1):
        if rel_improvement(baseline, loss) >= threshold:
            return step
    return None


def threshold_occupancy_from_losses(baseline: float, selected_losses: list[float | None], threshold: float) -> float:
    if not selected_losses:
        return 0.0
    return fmean(1.0 if rel_improvement(baseline, loss) >= threshold else 0.0 for loss in selected_losses)


def total_tokens(rows: list[dict[str, Any]]) -> int:
    total = 0
    for row in rows:
        total += int(row.get("total_tokens") or 0)
    return total


def record_from_run_dir(run_dir: Path, split: str) -> dict[str, Any] | None:
    summary_path = run_dir / "run_summary.json"
    manifest_path = run_dir / "run_manifest.json"
    if not summary_path.exists() or not manifest_path.exists():
        return None
    manifest = load_json(manifest_path)
    summary = load_json(summary_path)
    mode = str(manifest.get("task_mode_true") or "")
    worker = str(manifest.get("model_alias") or "")
    seed = manifest.get("instance_seed")
    if mode not in MODES or worker not in WORKERS or seed is None:
        return None
    rows = step_records(run_dir)
    baseline = safe_float(summary.get("baseline_loss"))
    best_loss = safe_float(summary.get("best_visible_loss"))
    best_loss = best_loss if math.isfinite(best_loss) else None
    final_loss = selected_final_loss(rows, best_loss)
    selected_losses = selected_loss_by_step(rows)
    best_losses = best_visible_by_step(baseline, selected_losses)
    tau_step = first_hit_step(baseline, best_losses, THRESHOLD)
    occupancy = threshold_occupancy_from_losses(baseline, selected_losses, THRESHOLD)
    return {
        "run_dir": str(run_dir),
        "run_id": str(summary.get("run_id") or run_dir.name),
        "completed_at": str(summary.get("completed_at") or ""),
        "split": split,
        "mode": mode,
        "worker": worker,
        "seed": int(seed),
        "baseline_loss": baseline,
        "best_loss": best_loss,
        "final_loss": final_loss,
        "success": tau_step is not None,
        "tau_step": tau_step,
        "steps_completed": int(summary.get("steps_completed") or len(rows) or 0),
        "elapsed_wall_seconds": safe_float(summary.get("elapsed_wall_seconds"), 0.0),
        "total_tokens": total_tokens(rows),
        "threshold_occupancy": occupancy,
        "final_relative_improvement": rel_improvement(baseline, final_loss),
        "selected_losses_by_step": selected_losses,
        "best_losses_by_step": best_losses,
    }


def load_frozen_runs(root: Path, n_per_cell: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_cell_seed: dict[tuple[str, str, int], dict[str, Any]] = {}
    for run_dir in sorted(root.glob("worker_confirmation_holdout_*/")):
        record = record_from_run_dir(run_dir, "holdout")
        if record is None:
            continue
        key = (record["mode"], record["worker"], record["seed"])
        previous = by_cell_seed.get(key)
        if previous is None or record["completed_at"] > previous["completed_at"]:
            by_cell_seed[key] = record

    frozen: list[dict[str, Any]] = []
    selection: dict[str, Any] = {"n_per_cell": n_per_cell, "cells": {}}
    for mode in MODES:
        for worker in WORKERS:
            candidates = [by_cell_seed[(mode, worker, seed)] for seed in sorted(seed for m, w, seed in by_cell_seed if m == mode and w == worker)]
            selected = candidates[: min(n_per_cell, WORKER_TARGETS[worker])]
            frozen.extend(selected)
            selection["cells"][f"{mode}/{worker}"] = {
                "available": len(candidates),
                "selected": len(selected),
                "seeds": [row["seed"] for row in selected],
            }
    return frozen, selection


def load_pooled_runs(
    campaign: Path,
    pilot_per_cell: int,
    holdout_per_cell: int,
    total_per_cell: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_split_cell_seed: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for split, pattern, root in [
        ("pilot", "worker_pilot_pilot_*/", campaign / "runs" / "worker_pilot"),
        ("holdout", "worker_confirmation_holdout_*/", campaign / "runs" / "worker_confirmation"),
    ]:
        for run_dir in sorted(root.glob(pattern)):
            record = record_from_run_dir(run_dir, split)
            if record is None:
                continue
            key = (split, record["mode"], record["worker"], record["seed"])
            previous = by_split_cell_seed.get(key)
            if previous is None or record["completed_at"] > previous["completed_at"]:
                by_split_cell_seed[key] = record

    rows: list[dict[str, Any]] = []
    selection: dict[str, Any] = {
        "worker_targets": WORKER_TARGETS if total_per_cell is None else {worker: total_per_cell for worker in WORKERS},
        "pilot_targets": PILOT_TARGETS,
        "holdout_per_cell": holdout_per_cell,
        "total_per_cell": total_per_cell,
        "cells": {},
    }
    for mode in MODES:
        for worker in WORKERS:
            cell_rows = []
            cell_info = {}
            target = total_per_cell if total_per_cell is not None else WORKER_TARGETS[worker]
            pilot_limit = min(pilot_per_cell, PILOT_TARGETS[worker], target)
            holdout_limit = min(holdout_per_cell, target - pilot_limit)
            for split, limit in [("pilot", pilot_limit), ("holdout", holdout_limit)]:
                candidates = [
                    by_split_cell_seed[(split, mode, worker, seed)]
                    for seed in sorted(seed for s, m, w, seed in by_split_cell_seed if s == split and m == mode and w == worker)
                ]
                selected = candidates[:limit]
                cell_rows.extend(selected)
                cell_info[split] = {
                    "available": len(candidates),
                    "selected": len(selected),
                    "seeds": [row["seed"] for row in selected],
                }
            if len(cell_rows) < target:
                used = {(row["split"], row["seed"]) for row in cell_rows}
                extras = [
                    by_split_cell_seed[(split, mode, worker, seed)]
                    for split in ["pilot", "holdout"]
                    for seed in sorted(seed for s, m, w, seed in by_split_cell_seed if s == split and m == mode and w == worker)
                    if (split, seed) not in used
                ]
                cell_rows.extend(extras[: target - len(cell_rows)])
            rows.extend(cell_rows)
            selection["cells"][f"{mode}/{worker}"] = {
                **cell_info,
                "selected": len(cell_rows),
                "seeds": [row["seed"] for row in cell_rows],
            }
    return rows, selection


def row_at_threshold(row: dict[str, Any], threshold: float, lambda_wall: float) -> dict[str, Any]:
    tau = first_hit_step(row["baseline_loss"], row["best_losses_by_step"], threshold)
    steps = max(int(row["steps_completed"]), 1)
    elapsed = float(row["elapsed_wall_seconds"])
    truncated_step = tau if tau is not None else steps
    c_gamma = lambda_wall * elapsed * max(int(truncated_step), 1) / steps
    failure = 0.0 if tau is not None else 1.0
    occupancy = threshold_occupancy_from_losses(row["baseline_loss"], row["selected_losses_by_step"], threshold)
    return {
        "tau_step": tau,
        "success": tau is not None,
        "failure": failure,
        "c_gamma": c_gamma,
        "deployment_loss": failure + c_gamma,
        "threshold_occupancy": occupancy,
    }


def deployment_loss(row: dict[str, Any], lambda_wall: float) -> float:
    return row_at_threshold(row, THRESHOLD, lambda_wall)["deployment_loss"]


def summarize_frontier(rows: list[dict[str, Any]], losses: dict[str, float], lambda_wall: float, threshold: float = THRESHOLD) -> list[dict[str, Any]]:
    out = []
    for mode in MODES:
        for worker in WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            threshold_rows = [row_at_threshold(row, threshold, lambda_wall) for row in cell]
            successes = sum(1 for row in threshold_rows if row["success"])
            p_smooth = (successes + 0.5) / (len(cell) + 1.0)
            hit_costs = [row["c_gamma"] for row in threshold_rows]
            kappa = statistics.median(hit_costs) if hit_costs else math.nan
            out.append(
                {
                    "mode": mode,
                    "worker": worker,
                    "threshold": threshold,
                    "run_count": len(cell),
                    "success_count": successes,
                    "success_rate": successes / len(cell) if cell else math.nan,
                    "mean_tau": fmean(row["tau_step"] for row in threshold_rows if row["tau_step"] is not None)
                    if any(row["tau_step"] is not None for row in threshold_rows)
                    else None,
                    "mean_c_gamma": fmean(row["c_gamma"] for row in threshold_rows),
                    "mean_failure_penalty": fmean(row["failure"] for row in threshold_rows),
                    "mean_occupancy": fmean(row["threshold_occupancy"] for row in threshold_rows),
                    "mean_final_relative_improvement": fmean(row["final_relative_improvement"] for row in cell),
                    "mean_elapsed_wall_seconds": fmean(row["elapsed_wall_seconds"] for row in cell),
                    "mean_total_tokens_millions": fmean(row["total_tokens"] / 1_000_000.0 for row in cell),
                    "deployment_loss_ci": bootstrap_ci([losses[row["run_id"]] for row in cell]),
                    "log_effort_objective": math.log(max(kappa, 1e-9)) - math.log(max(p_smooth, 1e-9)),
                }
            )
    return out


def measurement_loss(record: dict[str, Any], lambda_wall: float) -> float:
    signal = record.get("signal_level")
    signal_record = record.get("signal_record") or {}
    if signal in {"Z0", "Z1"}:
        return 0.0
    seconds = 0.0
    probe = signal_record.get("unmodified_baseline_probe") or {}
    seconds += safe_float(probe.get("total_seconds"), 0.0)
    if signal == "Z3":
        for item in signal_record.get("two_step_scout_trace") or []:
            seconds += safe_float(item.get("step_wall_seconds"), safe_float(item.get("selected_elapsed_wall_seconds"), 0.0))
    return lambda_wall * seconds


def router_analysis(router_path: Path | None, frontier: list[dict[str, Any]], mode_worker_loss: dict[tuple[str, str], float], lambda_wall: float) -> dict[str, Any]:
    if router_path is None or not router_path.exists():
        return {"available": False}
    rows = []
    for raw in router_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        output = item.get("router_output") or {}
        worker = output.get("selected_agent_model") or output.get("selected_worker")
        mode = ((item.get("instance") or {}).get("workload_id") or (item.get("signal_record") or {}).get("instance", {}).get("workload_id"))
        seed = ((item.get("instance") or {}).get("seed") or (item.get("signal_record") or {}).get("instance", {}).get("seed"))
        if mode not in MODES or worker not in WORKERS:
            continue
        rows.append(
            {
                "mode": mode,
                "seed": int(seed),
                "signal": item.get("signal_level"),
                "control": item.get("negative_control"),
                "worker": worker,
                "confidence": output.get("confidence"),
                "measurement_loss": measurement_loss(item, lambda_wall),
            }
        )

    score = {(row["mode"], row["worker"]): row["log_effort_objective"] for row in frontier}
    best_score = {mode: min(score[(mode, worker)] for worker in WORKERS) for mode in MODES}
    by_signal_control: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_signal_control[(row["signal"], row["control"])].append(row)

    selection_summary = []
    for (signal, control), items in sorted(by_signal_control.items()):
        counts = Counter(row["worker"] for row in items)
        regrets = [score[(row["mode"], row["worker"])] - best_score[row["mode"]] for row in items]
        selection_summary.append(
            {
                "signal": signal,
                "control": control,
                "records": len(items),
                "selected": dict(counts),
                "mean_log_effort_regret": fmean(regrets) if regrets else None,
            }
        )

    by_key = {(row["mode"], row["seed"], row["control"], row["signal"]): row for row in rows}
    gain_rows = []
    for row in rows:
        if row["signal"] == "Z0":
            continue
        base = by_key.get((row["mode"], row["seed"], row["control"], "Z0"))
        if base is None:
            continue
        base_loss = mode_worker_loss[(base["mode"], base["worker"])]
        routed_loss = mode_worker_loss[(row["mode"], row["worker"])]
        gain_rows.append(
            {
                "mode": row["mode"],
                "seed": row["seed"],
                "control": row["control"],
                "signal": row["signal"],
                "z0_worker": base["worker"],
                "zj_worker": row["worker"],
                "shift": base["worker"] != row["worker"],
                "gross_gain": base_loss - routed_loss,
                "measurement_loss": row["measurement_loss"],
                "net_gain": base_loss - routed_loss - row["measurement_loss"],
            }
        )

    gain_summary = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in gain_rows:
        grouped[(row["signal"], row["control"])].append(row)
    for (signal, control), items in sorted(grouped.items()):
        gains = [row["net_gain"] for row in items]
        gain_summary.append(
            {
                "signal": signal,
                "control": control,
                "pairs": len(items),
                "shift_rate": fmean(1.0 if row["shift"] else 0.0 for row in items),
                "net_gain_ci": bootstrap_ci(gains),
                "gross_gain_mean": fmean(row["gross_gain"] for row in items),
                "measurement_loss_mean": fmean(row["measurement_loss"] for row in items),
                "loss_increasing_shift_count": sum(1 for row in items if row["shift"] and row["net_gain"] < 0),
            }
        )
    return {
        "available": True,
        "router_path": str(router_path),
        "records": len(rows),
        "rows": rows,
        "frontier": frontier,
        "selection_summary": selection_summary,
        "gain_summary": gain_summary,
        "gain_rows": gain_rows,
    }


def save_all(fig: plt.Figure, out_dirs: list[Path], name: str) -> None:
    fig.tight_layout()
    for out_dir in out_dirs:
        out_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_dir / f"{name}.png", dpi=220, bbox_inches="tight")
        fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def worker_offset(index: int, width: float) -> float:
    return (index - (len(WORKERS) - 1) / 2.0) * width


def plot_frontier(frontier: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    x = np.arange(len(MODES))
    width = 0.25
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        means = [row["deployment_loss_ci"]["mean"] for row in rows]
        lo = [row["deployment_loss_ci"]["mean"] - row["deployment_loss_ci"]["lo"] for row in rows]
        hi = [row["deployment_loss_ci"]["hi"] - row["deployment_loss_ci"]["mean"] for row in rows]
        axes[0].bar(
            x + worker_offset(idx, width),
            means,
            width,
            yerr=[lo, hi],
            capsize=3,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
        axes[1].bar(
            x + worker_offset(idx, width),
            [row["log_effort_objective"] for row in rows],
            width,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend(loc="upper right")
    axes[0].set_ylabel("deployment loss")
    axes[0].set_title("Deployment loss")
    axes[1].set_ylabel("log-effort objective")
    axes[1].set_title("Certified log-effort surrogate")
    save_all(fig, out_dirs, "threeworker_frozen_confirmation_frontier")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        axes[0].bar(
            x + worker_offset(idx, width),
            [row["deployment_loss_ci"]["mean"] for row in rows],
            width,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
        axes[1].bar(
            x + worker_offset(idx, width),
            [row["log_effort_objective"] for row in rows],
            width,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend(loc="upper right")
    axes[0].set_ylabel("deployment loss")
    axes[0].set_title("Deployment loss")
    axes[1].set_ylabel("log-effort objective")
    axes[1].set_title("Certified log-effort surrogate")
    save_all(fig, out_dirs, "threeworker_deployment_frontier")


def plot_threshold(rows: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    thresholds = THRESHOLD_GRID
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for worker in WORKERS:
        cell = [row for row in rows if row["worker"] == worker]
        success_values = []
        tau_values = []
        for threshold in thresholds:
            stats = [row_at_threshold(row, threshold, 1.0) for row in cell]
            success_values.append(fmean(1.0 if item["success"] else 0.0 for item in stats) if stats else math.nan)
            hit_taus = [item["tau_step"] for item in stats if item["tau_step"] is not None]
            tau_values.append(statistics.median(hit_taus) if hit_taus else math.nan)
        axes[0].plot(thresholds, success_values, marker="o", linewidth=2.0, color=WORKER_COLORS[worker], label=WORKER_LABELS[worker])
        axes[1].plot(thresholds, tau_values, marker="s", linewidth=2.0, color=WORKER_COLORS[worker], label=WORKER_LABELS[worker])
    for ax in axes:
        ax.axvline(THRESHOLD, linestyle=":", color="#cc0000", linewidth=1.2)
        ax.set_xlabel("relative improvement threshold")
        ax.legend(loc="upper right")
    axes[0].set_ylabel("first-passage success probability")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].set_title("Threshold success")
    axes[1].set_ylabel("median first-hit step")
    axes[1].set_title("Time to threshold")
    save_all(fig, out_dirs, "threeworker_threshold_sensitivity")


def plot_router(router: dict[str, Any], out_dirs: list[Path]) -> None:
    if not router.get("available"):
        return
    real = [row for row in router["gain_summary"] if row["control"] == "none"]
    controls = [row for row in router["gain_summary"] if row["control"] != "none"]
    selection = [row for row in router["selection_summary"] if row["control"] == "none"]
    if selection:
        fig, axes = plt.subplots(1, 3, figsize=(13.8, 3.8))
        labels = [row["signal"] for row in selection]
        x = np.arange(len(labels))
        bottom = np.zeros(len(labels))
        for worker in WORKERS:
            vals = [row["selected"].get(worker, 0) / max(row["records"], 1) for row in selection]
            axes[0].bar(x, vals, bottom=bottom, label=WORKER_LABELS[worker], color=WORKER_COLORS[worker])
            bottom += np.array(vals)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(labels)
        axes[0].set_ylim(0.0, 1.0)
        axes[0].set_ylabel("selection share")
        axes[0].set_title("Router selections")
        axes[0].legend(loc="upper right")
        axes[1].bar(labels, [row["mean_log_effort_regret"] for row in selection], color="#666666")
        axes[1].set_ylabel("mean log-effort regret")
        axes[1].set_title("Allocation regret")
        mode_worker_loss = {
            (row["mode"], row["worker"]): row["deployment_loss_ci"]["mean"]
            for row in router.get("frontier", [])
        }
        real_rows = [row for row in router.get("rows", []) if row["control"] == "none"]
        if mode_worker_loss and real_rows:
            policies: list[tuple[str, float]] = []
            z0_rows = [row for row in real_rows if row["signal"] == "Z0"]
            for worker in WORKERS:
                values = [mode_worker_loss[(row["mode"], worker)] for row in z0_rows]
                policies.append((f"always\n{WORKER_LABELS[worker].replace('GPT-', '')}", fmean(values)))
            for signal in ["Z0", "Z1", "Z2", "Z3"]:
                values = [
                    mode_worker_loss[(row["mode"], row["worker"])] + row["measurement_loss"]
                    for row in real_rows
                    if row["signal"] == signal
                ]
                policies.append((signal, fmean(values)))
            oracle_values = [min(mode_worker_loss[(row["mode"], worker)] for worker in WORKERS) for row in z0_rows]
            policies.append(("oracle\nmode", fmean(oracle_values)))
            px = np.arange(len(policies))
            policy_colors = ["#b9b9b9"] * len(WORKERS) + ["#7aa6c2"] * 4 + ["#4f9d69"]
            axes[2].bar(
                px,
                [value for _, value in policies],
                color=policy_colors,
            )
            axes[2].set_xticks(px)
            axes[2].set_xticklabels([label for label, _ in policies], rotation=30, ha="right", fontsize=8)
            axes[2].set_ylabel("mean deployment loss")
            axes[2].set_title("Policy and oracle gap")
        save_all(fig, out_dirs, "threeworker_router_selection_regret")
    if real:
        fig, ax = plt.subplots(figsize=(6.2, 3.4))
        labels = [row["signal"] for row in real]
        means = [row["net_gain_ci"]["mean"] for row in real]
        lo = [row["net_gain_ci"]["mean"] - row["net_gain_ci"]["lo"] for row in real]
        hi = [row["net_gain_ci"]["hi"] - row["net_gain_ci"]["mean"] for row in real]
        ax.axhline(0.0, color="#444444", linewidth=1.0)
        ax.bar(labels, means, yerr=[lo, hi], capsize=3, color="#2a6fdb")
        ax.set_ylabel("paired net deployment gain")
        ax.set_title("Real signals versus Z0")
        save_all(fig, out_dirs, "threeworker_router_paired_gain")
    if controls:
        fig, ax = plt.subplots(figsize=(8.8, 3.7))
        labels = [f'{row["signal"]}\\n{row["control"]}' for row in controls]
        means = [row["net_gain_ci"]["mean"] for row in controls]
        ax.axhline(0.0, color="#444444", linewidth=1.0)
        ax.bar(np.arange(len(labels)), means, color="#999999")
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("paired net deployment gain")
        ax.set_title("Negative-control signal checks")
        save_all(fig, out_dirs, "threeworker_negative_controls")


def plot_crossover(frontier: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    x = np.arange(len(MODES))
    width = 0.25
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        axes[0].bar(
            x + worker_offset(idx, width),
            [row["success_count"] / row["run_count"] for row in rows],
            width,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
        axes[1].bar(
            x + worker_offset(idx, width),
            [row["mean_elapsed_wall_seconds"] / 60.0 for row in rows],
            width,
            label=WORKER_LABELS[worker],
            color=WORKER_COLORS[worker],
        )
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend(loc="upper right")
    axes[0].set_ylim(0.0, 1.01)
    axes[0].set_ylabel("first-passage success")
    axes[0].set_title("Retry-crossover success condition")
    axes[1].set_ylabel("mean wall-clock minutes")
    axes[1].set_title("Worker-side cost condition")
    save_all(fig, out_dirs, "threeworker_crossover_applicability")


def frontier_for_threshold(rows: list[dict[str, Any]], lambda_wall: float, threshold: float) -> list[dict[str, Any]]:
    losses = {row["run_id"]: row_at_threshold(row, threshold, lambda_wall)["deployment_loss"] for row in rows}
    return summarize_frontier(rows, losses, lambda_wall, threshold)


def winner_string(frontier: list[dict[str, Any]], metric: str) -> str:
    labels = []
    for mode in MODES:
        cell = [row for row in frontier if row["mode"] == mode]
        if metric == "deployment_loss":
            best = min(cell, key=lambda row: row["deployment_loss_ci"]["mean"])
        elif metric == "log_effort":
            best = min(cell, key=lambda row: row["log_effort_objective"])
        else:
            raise ValueError(metric)
        labels.append(WORKER_SHORT[best["worker"]])
    return "/".join(labels)


def threshold_analysis(rows: list[dict[str, Any]], lambda_wall: float) -> dict[str, Any]:
    frontiers = {str(threshold): frontier_for_threshold(rows, lambda_wall, threshold) for threshold in THRESHOLD_GRID}
    primary_frontier = frontiers[str(THRESHOLD)]
    primary_dep = winner_string(primary_frontier, "deployment_loss")
    primary_log = winner_string(primary_frontier, "log_effort")
    summary_rows = []
    for threshold in MAIN_THRESHOLDS:
        threshold_rows = []
        for worker in WORKERS:
            worker_rows = [row for row in rows if row["worker"] == worker]
            stats = [row_at_threshold(row, threshold, lambda_wall) for row in worker_rows]
            threshold_rows.append(
                {
                    "worker": worker,
                    "pooled_success_rate": fmean(1.0 if stat["success"] else 0.0 for stat in stats),
                    "pooled_c_gamma": fmean(stat["c_gamma"] for stat in stats),
                    "pooled_deployment_loss": fmean(stat["deployment_loss"] for stat in stats),
                }
            )
        frontier = frontiers[str(threshold)]
        dep_winners = winner_string(frontier, "deployment_loss")
        log_winners = winner_string(frontier, "log_effort")
        summary_rows.append(
            {
                "threshold": threshold,
                "deployment_winners_by_mode": dep_winners,
                "log_effort_winners_by_mode": log_winners,
                "pooled_by_worker": threshold_rows,
                "changes_vs_primary": "same" if dep_winners == primary_dep and log_winners == primary_log else "changes",
            }
        )
    return {
        "mode_order": MODES,
        "worker_code": WORKER_SHORT,
        "frontiers": frontiers,
        "summary": summary_rows,
    }


def router_threshold_analysis(router: dict[str, Any], rows: list[dict[str, Any]], lambda_wall: float) -> list[dict[str, Any]]:
    if not router.get("available"):
        return []
    decisions = router.get("rows", [])
    out = []
    for threshold in THRESHOLD_GRID:
        mode_worker_loss = {}
        for mode in MODES:
            for worker in WORKERS:
                cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
                mode_worker_loss[(mode, worker)] = fmean(row_at_threshold(row, threshold, lambda_wall)["deployment_loss"] for row in cell)
        by_key = {(row["mode"], row["seed"], row["control"], row["signal"]): row for row in decisions}
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in decisions:
            if row["signal"] == "Z0":
                continue
            base = by_key.get((row["mode"], row["seed"], row["control"], "Z0"))
            if base is None:
                continue
            gross_gain = mode_worker_loss[(base["mode"], base["worker"])] - mode_worker_loss[(row["mode"], row["worker"])]
            grouped[(row["signal"], row["control"])].append(
                {
                    "shift": base["worker"] != row["worker"],
                    "gross_gain": gross_gain,
                    "measurement_loss": row["measurement_loss"],
                    "net_gain": gross_gain - row["measurement_loss"],
                }
            )
        for (signal, control), items in sorted(grouped.items()):
            out.append(
                {
                    "threshold": threshold,
                    "signal": signal,
                    "control": control,
                    "pairs": len(items),
                    "shift_rate": fmean(1.0 if row["shift"] else 0.0 for row in items),
                    "gross_gain_mean": fmean(row["gross_gain"] for row in items),
                    "measurement_loss_mean": fmean(row["measurement_loss"] for row in items),
                    "net_gain_mean": fmean(row["net_gain"] for row in items),
                    "any_positive_net_gain": any(row["net_gain"] > 0.0 for row in items),
                }
            )
    return out


def plot_improvement_distribution(rows: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    rng = np.random.default_rng(20260507)
    fig, ax = plt.subplots(figsize=(10.5, 4.0))
    width = 0.25
    x = np.arange(len(MODES))
    for idx, worker in enumerate(WORKERS):
        positions = x + worker_offset(idx, width)
        data = [[row["final_relative_improvement"] for row in rows if row["mode"] == mode and row["worker"] == worker] for mode in MODES]
        ax.boxplot(
            data,
            positions=positions,
            widths=width * 0.8,
            patch_artist=True,
            boxprops={"facecolor": WORKER_COLORS[worker], "alpha": 0.22, "edgecolor": WORKER_COLORS[worker]},
            medianprops={"color": WORKER_COLORS[worker], "linewidth": 2},
            whiskerprops={"color": WORKER_COLORS[worker]},
            capprops={"color": WORKER_COLORS[worker]},
            flierprops={"marker": ""},
        )
        for pos, values in zip(positions, data):
            jitter = rng.normal(0.0, width * 0.10, size=len(values))
            ax.scatter(np.full(len(values), pos) + jitter, values, color=WORKER_COLORS[worker], s=18, alpha=0.45)
    ax.axhline(THRESHOLD, linestyle=":", color="#cc0000", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
    ax.set_ylabel("final relative improvement")
    ax.set_title("Final improvement distribution")
    handles = [plt.Line2D([0], [0], color=WORKER_COLORS[w], lw=4, label=WORKER_LABELS[w]) for w in WORKERS]
    ax.legend(handles=handles, loc="upper right")
    save_all(fig, out_dirs, "threeworker_improvement_distribution")


def plot_tau_distribution(rows: list[dict[str, Any]], out_dirs: list[Path], lambda_wall: float) -> None:
    rng = np.random.default_rng(20260507)
    fig, ax = plt.subplots(figsize=(10.5, 4.0))
    width = 0.25
    x = np.arange(len(MODES))
    horizon = max((row["steps_completed"] for row in rows), default=20)
    for idx, worker in enumerate(WORKERS):
        for mode_idx, mode in enumerate(MODES):
            cell = [row_at_threshold(row, THRESHOLD, lambda_wall) for row in rows if row["mode"] == mode and row["worker"] == worker]
            values = [item["tau_step"] if item["tau_step"] is not None else horizon + 1 for item in cell]
            pos = mode_idx + worker_offset(idx, width)
            jitter = rng.normal(0.0, width * 0.12, size=len(values))
            ax.scatter(np.full(len(values), pos) + jitter, values, color=WORKER_COLORS[worker], s=18, alpha=0.5)
            if values:
                ax.plot([pos - width * 0.32, pos + width * 0.32], [statistics.median(values)] * 2, color=WORKER_COLORS[worker], lw=2.2)
    ax.axhline(horizon + 0.5, linestyle="--", color="#777777", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
    ax.set_ylabel(r"first-hit step $\tau_\gamma$; failures at H+1")
    ax.set_title("First-hit distribution")
    handles = [plt.Line2D([0], [0], marker="o", linestyle="", color=WORKER_COLORS[w], label=WORKER_LABELS[w]) for w in WORKERS]
    ax.legend(handles=handles, loc="upper right")
    save_all(fig, out_dirs, "threeworker_tau_distribution")


def plot_trajectories(rows: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    max_steps = max((row["steps_completed"] for row in rows), default=20)
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 3.8), sharey=True)
    for ax, mode in zip(axes, MODES):
        for worker in WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            traces = []
            for row in cell:
                values = [rel_improvement(row["baseline_loss"], loss) for loss in row["best_losses_by_step"]]
                if not values:
                    continue
                if len(values) < max_steps:
                    values = values + [values[-1]] * (max_steps - len(values))
                traces.append(values[:max_steps])
            if not traces:
                continue
            arr = np.array(traces, dtype=float)
            steps = np.arange(1, max_steps + 1)
            mean = np.mean(arr, axis=0)
            lo = np.quantile(arr, 0.25, axis=0)
            hi = np.quantile(arr, 0.75, axis=0)
            ax.plot(steps, mean, color=WORKER_COLORS[worker], lw=2.0, label=WORKER_LABELS[worker])
            ax.fill_between(steps, lo, hi, color=WORKER_COLORS[worker], alpha=0.14)
        ax.axhline(THRESHOLD, linestyle=":", color="#cc0000", linewidth=1.1)
        ax.set_title(MODE_LABELS[mode])
        ax.set_xlabel("step")
    axes[0].set_ylabel("best visible relative improvement")
    axes[-1].legend(loc="lower right")
    save_all(fig, out_dirs, "threeworker_relative_improvement_trajectories")


def plot_cost_quality(rows: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for worker in WORKERS:
        cell = [row for row in rows if row["worker"] == worker]
        axes[0].scatter(
            [row["elapsed_wall_seconds"] / 60.0 for row in cell],
            [row["final_relative_improvement"] for row in cell],
            color=WORKER_COLORS[worker],
            s=24,
            alpha=0.45,
            label=WORKER_LABELS[worker],
        )
        axes[1].scatter(
            [row["total_tokens"] / 1_000_000.0 for row in cell],
            [row["final_relative_improvement"] for row in cell],
            color=WORKER_COLORS[worker],
            s=24,
            alpha=0.45,
            label=WORKER_LABELS[worker],
        )
    for ax in axes:
        ax.axhline(THRESHOLD, linestyle=":", color="#cc0000", linewidth=1.1)
        ax.set_ylabel("final relative improvement")
        ax.legend(loc="upper right")
    axes[0].set_xlabel("wall time per run (minutes)")
    axes[0].set_title("Quality vs wall-clock")
    axes[1].set_xlabel("total tokens per run (millions)")
    axes[1].set_title("Quality vs token accounting")
    save_all(fig, out_dirs, "threeworker_worker_cost_quality_diagnostics")


def plot_cost_to_tau(rows: list[dict[str, Any]], out_dirs: list[Path], lambda_wall: float) -> None:
    rng = np.random.default_rng(20260507)
    fig, ax = plt.subplots(figsize=(10.5, 4.0))
    width = 0.25
    x = np.arange(len(MODES))
    for idx, worker in enumerate(WORKERS):
        for mode_idx, mode in enumerate(MODES):
            cell = [row_at_threshold(row, THRESHOLD, lambda_wall) for row in rows if row["mode"] == mode and row["worker"] == worker]
            values = [item["c_gamma"] for item in cell]
            pos = mode_idx + worker_offset(idx, width)
            jitter = rng.normal(0.0, width * 0.12, size=len(values))
            ax.scatter(np.full(len(values), pos) + jitter, values, color=WORKER_COLORS[worker], s=18, alpha=0.5)
            if values:
                ax.plot([pos - width * 0.32, pos + width * 0.32], [statistics.median(values)] * 2, color=WORKER_COLORS[worker], lw=2.2)
    ax.set_xticks(x)
    ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
    ax.set_ylabel(r"normalized wall cost $C_\gamma$")
    ax.set_title("Cost accumulated to first hit or horizon")
    handles = [plt.Line2D([0], [0], marker="o", linestyle="", color=WORKER_COLORS[w], label=WORKER_LABELS[w]) for w in WORKERS]
    ax.legend(handles=handles, loc="upper right")
    save_all(fig, out_dirs, "threeworker_cost_to_tau_by_mode_worker")


def clean_json(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def write_outputs(
    accounting_dir: Path,
    frontier: list[dict[str, Any]],
    threshold_report: dict[str, Any],
    router: dict[str, Any],
    router_threshold: list[dict[str, Any]],
) -> None:
    frontier_rows = []
    for row in frontier:
        frontier_rows.append(
            {
                "mode": row["mode"],
                "worker": row["worker"],
                "run_count": row["run_count"],
                "success_count": row["success_count"],
                "success_rate": row["success_rate"],
                "mean_tau": row["mean_tau"],
                "mean_c_gamma": row["mean_c_gamma"],
                "mean_failure_penalty": row["mean_failure_penalty"],
                "mean_deployment_loss": row["deployment_loss_ci"]["mean"],
                "log_effort_objective": row["log_effort_objective"],
                "mean_final_relative_improvement": row["mean_final_relative_improvement"],
                "mean_elapsed_wall_minutes": row["mean_elapsed_wall_seconds"] / 60.0,
                "mean_total_tokens_millions": row["mean_total_tokens_millions"],
            }
        )
    write_csv(
        accounting_dir / "threeworker_frontier_summary.csv",
        frontier_rows,
        [
            "mode",
            "worker",
            "run_count",
            "success_count",
            "success_rate",
            "mean_tau",
            "mean_c_gamma",
            "mean_failure_penalty",
            "mean_deployment_loss",
            "log_effort_objective",
            "mean_final_relative_improvement",
            "mean_elapsed_wall_minutes",
            "mean_total_tokens_millions",
        ],
    )

    threshold_rows = []
    for row in threshold_report["summary"]:
        values = {
            "threshold": row["threshold"],
            "deployment_winners_by_mode": row["deployment_winners_by_mode"],
            "log_effort_winners_by_mode": row["log_effort_winners_by_mode"],
            "changes_vs_primary": row["changes_vs_primary"],
        }
        for item in row["pooled_by_worker"]:
            code = WORKER_SHORT[item["worker"]]
            values[f"success_{code}"] = item["pooled_success_rate"]
            values[f"c_gamma_{code}"] = item["pooled_c_gamma"]
            values[f"deployment_loss_{code}"] = item["pooled_deployment_loss"]
        threshold_rows.append(values)
    write_csv(
        accounting_dir / "threeworker_threshold_summary.csv",
        threshold_rows,
        [
            "threshold",
            "deployment_winners_by_mode",
            "log_effort_winners_by_mode",
            "deployment_loss_C",
            "deployment_loss_4",
            "deployment_loss_m",
            "c_gamma_C",
            "c_gamma_4",
            "c_gamma_m",
            "success_C",
            "success_4",
            "success_m",
            "changes_vs_primary",
        ],
    )

    if router.get("available"):
        write_csv(
            accounting_dir / "threeworker_router_selection_summary.csv",
            router["selection_summary"],
            ["signal", "control", "records", "selected", "mean_log_effort_regret"],
        )
        write_csv(
            accounting_dir / "threeworker_router_gain_summary.csv",
            [
                {
                    "signal": row["signal"],
                    "control": row["control"],
                    "pairs": row["pairs"],
                    "shift_rate": row["shift_rate"],
                    "gross_gain_mean": row["gross_gain_mean"],
                    "measurement_loss_mean": row["measurement_loss_mean"],
                    "net_gain_mean": row["net_gain_ci"]["mean"],
                    "net_gain_lo": row["net_gain_ci"]["lo"],
                    "net_gain_hi": row["net_gain_ci"]["hi"],
                    "loss_increasing_shift_count": row["loss_increasing_shift_count"],
                }
                for row in router["gain_summary"]
            ],
            [
                "signal",
                "control",
                "pairs",
                "shift_rate",
                "gross_gain_mean",
                "measurement_loss_mean",
                "net_gain_mean",
                "net_gain_lo",
                "net_gain_hi",
                "loss_increasing_shift_count",
            ],
        )
        write_csv(
            accounting_dir / "threeworker_router_threshold_summary.csv",
            router_threshold,
            [
                "threshold",
                "signal",
                "control",
                "pairs",
                "shift_rate",
                "gross_gain_mean",
                "measurement_loss_mean",
                "net_gain_mean",
                "any_positive_net_gain",
            ],
        )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", default="autoresearch/campaigns/h20_delta005_20260505")
    parser.add_argument("--n-per-cell", type=int, default=25)
    parser.add_argument("--pilot-per-cell", type=int, default=10)
    parser.add_argument("--pooled", action="store_true")
    parser.add_argument("--total-per-cell", type=int, default=None)
    parser.add_argument("--router-decisions", default=None)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--accounting-dir", default=None)
    parser.add_argument("--paper-fig-dir", default="autoresearch/paper_figures/current")
    parser.add_argument("--campaign-fig-dir", default="autoresearch/campaigns/h20_delta005_20260505/figures/current_snapshot")
    parser.add_argument("--lambda-wall", type=float, default=1.0 / 1800.0)
    args = parser.parse_args()

    campaign = Path(args.campaign_root)
    if args.pooled:
        rows, selection = load_pooled_runs(campaign, args.pilot_per_cell, args.n_per_cell, args.total_per_cell)
        analysis_label = "pooled_pilot_holdout"
    else:
        rows, selection = load_frozen_runs(campaign / "runs" / "worker_confirmation", args.n_per_cell)
        analysis_label = "holdout_only"
    losses = {row["run_id"]: deployment_loss(row, args.lambda_wall) for row in rows}
    frontier = summarize_frontier(rows, losses, args.lambda_wall)
    mode_worker_loss = {
        (row["mode"], row["worker"]): row["deployment_loss_ci"]["mean"]
        for row in frontier
    }
    router_path = Path(args.router_decisions) if args.router_decisions else None
    router = router_analysis(router_path, frontier, mode_worker_loss, args.lambda_wall)
    threshold_report = threshold_analysis(rows, args.lambda_wall)
    router_threshold = router_threshold_analysis(router, rows, args.lambda_wall)

    report = {
        "threshold": THRESHOLD,
        "threshold_grid": THRESHOLD_GRID,
        "lambda_wall": args.lambda_wall,
        "analysis_label": analysis_label,
        "frozen_selection": selection,
        "frozen_run_count": len(rows),
        "frontier": frontier,
        "threshold_analysis": threshold_report,
        "router": router,
        "router_threshold_analysis": router_threshold,
    }
    output = Path(args.output_json) if args.output_json else campaign / "accounting" / "threeworker_final_analysis.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(clean_json(report), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    accounting_dir = Path(args.accounting_dir) if args.accounting_dir else output.parent
    write_outputs(accounting_dir, frontier, threshold_report, router, router_threshold)

    fig_dirs = [Path(args.paper_fig_dir), Path(args.campaign_fig_dir)]
    plot_frontier(frontier, fig_dirs)
    plot_threshold(rows, fig_dirs)
    plot_router(router, fig_dirs)
    plot_crossover(frontier, fig_dirs)
    plot_improvement_distribution(rows, fig_dirs)
    plot_tau_distribution(rows, fig_dirs, args.lambda_wall)
    plot_trajectories(rows, fig_dirs)
    plot_cost_quality(rows, fig_dirs)
    plot_cost_to_tau(rows, fig_dirs, args.lambda_wall)
    print(json.dumps({"output": str(output), "analysis_label": analysis_label, "run_count": len(rows), "router_available": router["available"]}, indent=2))


if __name__ == "__main__":
    main()
