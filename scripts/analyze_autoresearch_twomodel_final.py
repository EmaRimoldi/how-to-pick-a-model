"""Frozen two-model analysis for the AutoResearch CIFAR-10 paper experiments."""

from __future__ import annotations

import argparse
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


MODES = ["cnn_compact", "mlp_flat", "resnet_micro"]
MODE_LABELS = {"cnn_compact": "CNN", "mlp_flat": "MLP", "resnet_micro": "ResNet"}
WORKERS = ["gpt_5_3_codex", "gpt_5_4"]
WORKER_LABELS = {"gpt_5_3_codex": "GPT-5.3 Codex", "gpt_5_4": "GPT-5.4"}
THRESHOLD = 0.05


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
    occupancy = statistics.fmean(1.0 if row.get("successful_step") else 0.0 for row in rows) if rows else 0.0
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
        "success": rel_improvement(baseline, best_loss) >= THRESHOLD,
        "tau_step": summary.get("tau_step"),
        "steps_completed": int(summary.get("steps_completed") or len(rows) or 0),
        "elapsed_wall_seconds": safe_float(summary.get("elapsed_wall_seconds"), 0.0),
        "total_tokens": total_tokens(rows),
        "threshold_occupancy": occupancy,
        "final_relative_improvement": rel_improvement(baseline, final_loss),
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
            selected = candidates[:n_per_cell]
            frozen.extend(selected)
            selection["cells"][f"{mode}/{worker}"] = {
                "available": len(candidates),
                "selected": len(selected),
                "seeds": [row["seed"] for row in selected],
            }
    return frozen, selection


def load_pooled_runs(campaign: Path, pilot_per_cell: int, holdout_per_cell: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        "pilot_per_cell": pilot_per_cell,
        "holdout_per_cell": holdout_per_cell,
        "n_per_cell": pilot_per_cell + holdout_per_cell,
        "cells": {},
    }
    for mode in MODES:
        for worker in WORKERS:
            cell_rows = []
            cell_info = {}
            for split, limit in [("pilot", pilot_per_cell), ("holdout", holdout_per_cell)]:
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
            rows.extend(cell_rows)
            selection["cells"][f"{mode}/{worker}"] = {
                **cell_info,
                "selected": len(cell_rows),
                "seeds": [row["seed"] for row in cell_rows],
            }
    return rows, selection


def deployment_loss(row: dict[str, Any], lambda_wall: float) -> float:
    failure = 0.0 if row["success"] else 1.0
    occupancy_penalty = 1.0 - float(row["threshold_occupancy"])
    quality_penalty = 1.0 - max(0.0, min(1.0, float(row["final_relative_improvement"])))
    return failure + 0.25 * occupancy_penalty + 0.25 * quality_penalty + lambda_wall * float(row["elapsed_wall_seconds"])


def summarize_frontier(rows: list[dict[str, Any]], losses: dict[str, float]) -> list[dict[str, Any]]:
    out = []
    for mode in MODES:
        for worker in WORKERS:
            cell = [row for row in rows if row["mode"] == mode and row["worker"] == worker]
            successes = sum(1 for row in cell if row["success"])
            p_smooth = (successes + 0.5) / (len(cell) + 1.0)
            hit_costs = []
            for row in cell:
                tau = row["tau_step"]
                steps = max(int(row["steps_completed"]), 1)
                elapsed = float(row["elapsed_wall_seconds"])
                hit_costs.append(elapsed * max(int(tau or steps), 1) / steps)
            kappa = statistics.median(hit_costs) if hit_costs else math.nan
            out.append(
                {
                    "mode": mode,
                    "worker": worker,
                    "run_count": len(cell),
                    "success_count": successes,
                    "success_rate": successes / len(cell) if cell else math.nan,
                    "mean_tau": statistics.fmean(row["tau_step"] for row in cell if row["tau_step"] is not None)
                    if any(row["tau_step"] is not None for row in cell)
                    else None,
                    "mean_occupancy": statistics.fmean(row["threshold_occupancy"] for row in cell),
                    "mean_final_relative_improvement": statistics.fmean(row["final_relative_improvement"] for row in cell),
                    "mean_elapsed_wall_seconds": statistics.fmean(row["elapsed_wall_seconds"] for row in cell),
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
                "mean_log_effort_regret": statistics.fmean(regrets) if regrets else None,
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
                "shift_rate": statistics.fmean(1.0 if row["shift"] else 0.0 for row in items),
                "net_gain_ci": bootstrap_ci(gains),
                "gross_gain_mean": statistics.fmean(row["gross_gain"] for row in items),
                "measurement_loss_mean": statistics.fmean(row["measurement_loss"] for row in items),
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


def plot_frontier(frontier: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    x = np.arange(len(MODES))
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        means = [row["deployment_loss_ci"]["mean"] for row in rows]
        lo = [row["deployment_loss_ci"]["mean"] - row["deployment_loss_ci"]["lo"] for row in rows]
        hi = [row["deployment_loss_ci"]["hi"] - row["deployment_loss_ci"]["mean"] for row in rows]
        axes[0].bar(x + (idx - 0.5) * width, means, width, yerr=[lo, hi], capsize=3, label=WORKER_LABELS[worker])
        axes[1].bar(x + (idx - 0.5) * width, [row["log_effort_objective"] for row in rows], width, label=WORKER_LABELS[worker])
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend()
    axes[0].set_ylabel("deployment loss")
    axes[0].set_title("Pooled deployment loss, n=35/cell")
    axes[1].set_ylabel("log-effort objective")
    axes[1].set_title("Certified log-effort surrogate")
    save_all(fig, out_dirs, "twomodel_frozen_confirmation_frontier")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        axes[0].bar(x + (idx - 0.5) * width, [row["deployment_loss_ci"]["mean"] for row in rows], width, label=WORKER_LABELS[worker])
        axes[1].bar(x + (idx - 0.5) * width, [row["log_effort_objective"] for row in rows], width, label=WORKER_LABELS[worker])
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend()
    axes[0].set_ylabel("deployment loss")
    axes[0].set_title("Pooled deployment loss, n=35/cell")
    axes[1].set_ylabel("log-effort objective")
    axes[1].set_title("Certified log-effort surrogate")
    save_all(fig, out_dirs, "twomodel_deployment_frontier")


def plot_threshold(rows: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    thresholds = [0.01, 0.02, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    colors = {"gpt_5_3_codex": "#f58518", "gpt_5_4": "#54a24b"}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for worker in WORKERS:
        cell = [row for row in rows if row["worker"] == worker]
        success_values = []
        tau_values = []
        for threshold in thresholds:
            successes = [row for row in cell if row["final_relative_improvement"] >= threshold]
            success_values.append(len(successes) / len(cell) if cell else math.nan)
            hit_taus = [row["tau_step"] for row in cell if row["final_relative_improvement"] >= threshold and row["tau_step"] is not None]
            tau_values.append(statistics.median(hit_taus) if hit_taus else math.nan)
        axes[0].plot(thresholds, success_values, marker="o", linewidth=2.0, color=colors[worker], label=WORKER_LABELS[worker])
        axes[1].plot(thresholds, tau_values, marker="s", linewidth=2.0, color=colors[worker], label=WORKER_LABELS[worker])
    for ax in axes:
        ax.axvline(THRESHOLD, linestyle=":", color="#cc0000", linewidth=1.2)
        ax.set_xlabel("relative improvement threshold")
        ax.legend()
    axes[0].set_ylabel("first-passage success probability")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].set_title("Threshold success")
    axes[1].set_ylabel("median first-hit step")
    axes[1].set_title("Time to threshold")
    save_all(fig, out_dirs, "twomodel_threshold_sensitivity")


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
        colors = {"gpt_5_3_codex": "#5b8fd6", "gpt_5_4": "#d6814b"}
        for worker in WORKERS:
            vals = [row["selected"].get(worker, 0) / max(row["records"], 1) for row in selection]
            axes[0].bar(x, vals, bottom=bottom, label=WORKER_LABELS[worker], color=colors[worker])
            bottom += np.array(vals)
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(labels)
        axes[0].set_ylim(0.0, 1.0)
        axes[0].set_ylabel("selection share")
        axes[0].set_title("Router selections")
        axes[0].legend()
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
                policies.append((f"always\n{WORKER_LABELS[worker].replace('GPT-', '')}", statistics.fmean(values)))
            for signal in ["Z0", "Z1", "Z2", "Z3"]:
                values = [
                    mode_worker_loss[(row["mode"], row["worker"])] + row["measurement_loss"]
                    for row in real_rows
                    if row["signal"] == signal
                ]
                policies.append((signal, statistics.fmean(values)))
            oracle_values = [min(mode_worker_loss[(row["mode"], worker)] for worker in WORKERS) for row in z0_rows]
            policies.append(("oracle\nmode", statistics.fmean(oracle_values)))
            px = np.arange(len(policies))
            axes[2].bar(
                px,
                [value for _, value in policies],
                color=["#b9b9b9", "#b9b9b9", "#7aa6c2", "#7aa6c2", "#7aa6c2", "#7aa6c2", "#4f9d69"],
            )
            axes[2].set_xticks(px)
            axes[2].set_xticklabels([label for label, _ in policies], rotation=30, ha="right", fontsize=8)
            axes[2].set_ylabel("mean deployment loss")
            axes[2].set_title("Policy and oracle gap")
        save_all(fig, out_dirs, "twomodel_router_selection_regret")
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
        save_all(fig, out_dirs, "twomodel_router_paired_gain")
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
        save_all(fig, out_dirs, "twomodel_negative_controls")


def plot_crossover(frontier: list[dict[str, Any]], out_dirs: list[Path]) -> None:
    x = np.arange(len(MODES))
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for idx, worker in enumerate(WORKERS):
        rows = [next(row for row in frontier if row["mode"] == mode and row["worker"] == worker) for mode in MODES]
        axes[0].bar(x + (idx - 0.5) * width, [row["success_count"] / row["run_count"] for row in rows], width, label=WORKER_LABELS[worker])
        axes[1].bar(x + (idx - 0.5) * width, [row["mean_elapsed_wall_seconds"] / 60.0 for row in rows], width, label=WORKER_LABELS[worker])
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([MODE_LABELS[mode] for mode in MODES])
        ax.legend()
    axes[0].set_ylim(0.85, 1.01)
    axes[0].set_ylabel("first-passage success")
    axes[0].set_title("Retry-crossover success condition")
    axes[1].set_ylabel("mean wall-clock minutes")
    axes[1].set_title("Worker-side cost condition")
    save_all(fig, out_dirs, "twomodel_crossover_applicability")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", default="campaigns/autoresearch_cifar10_h20_delta005_20260505")
    parser.add_argument("--n-per-cell", type=int, default=25)
    parser.add_argument("--pilot-per-cell", type=int, default=10)
    parser.add_argument("--pooled", action="store_true")
    parser.add_argument("--router-decisions", default=None)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--paper-fig-dir", default="paper_overleaf/figures/autoresearch")
    parser.add_argument("--campaign-fig-dir", default="campaigns/autoresearch_cifar10_h20_delta005_20260505/figures/current_snapshot")
    parser.add_argument("--lambda-wall", type=float, default=1.0 / 1800.0)
    args = parser.parse_args()

    campaign = Path(args.campaign_root)
    if args.pooled:
        rows, selection = load_pooled_runs(campaign, args.pilot_per_cell, args.n_per_cell)
        analysis_label = "pooled_pilot_holdout"
    else:
        rows, selection = load_frozen_runs(campaign / "runs" / "worker_confirmation", args.n_per_cell)
        analysis_label = "holdout_only"
    losses = {row["run_id"]: deployment_loss(row, args.lambda_wall) for row in rows}
    frontier = summarize_frontier(rows, losses)
    mode_worker_loss = {
        (row["mode"], row["worker"]): row["deployment_loss_ci"]["mean"]
        for row in frontier
    }
    router_path = Path(args.router_decisions) if args.router_decisions else None
    router = router_analysis(router_path, frontier, mode_worker_loss, args.lambda_wall)

    report = {
        "threshold": THRESHOLD,
        "lambda_wall": args.lambda_wall,
        "analysis_label": analysis_label,
        "frozen_selection": selection,
        "frozen_run_count": len(rows),
        "frontier": frontier,
        "router": router,
    }
    output = Path(args.output_json) if args.output_json else campaign / "accounting" / "twomodel_final_analysis.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")

    fig_dirs = [Path(args.paper_fig_dir), Path(args.campaign_fig_dir)]
    plot_frontier(frontier, fig_dirs)
    plot_threshold(rows, fig_dirs)
    plot_router(router, fig_dirs)
    plot_crossover(frontier, fig_dirs)
    print(json.dumps({"output": str(output), "analysis_label": analysis_label, "run_count": len(rows), "router_available": router["available"]}, indent=2))


if __name__ == "__main__":
    main()
