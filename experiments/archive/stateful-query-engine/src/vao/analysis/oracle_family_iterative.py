"""Iterative multi-step oracle-family analysis with action-routing diagnostics."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vao.analysis.task_mode_decomposition import (
    EPS,
    _filter_complete_models,
    _task_mode_priors,
    choose_router,
    mutual_information,
    pairwise_model_terms,
    routing_mismatch,
    routing_objective,
    routing_triviality,
    summarize_models,
)
from vao.estimators import gains_by_mode, productive_mode_proxy, routing_mismatch_jsd, routing_regret
from vao.logging_utils import read_jsonl
from vao.records import iter_run_dirs
from vao.schemas import StepRecord
from vao.task_modes import TASK_MODE_SET, task_mode_from_instance_overrides
from vao.taxonomy import MODES


@dataclass(frozen=True)
class Trajectory:
    run_dir: Path
    run_id: str
    split: str
    model_id: str
    model_alias: str | None
    task_mode_true: str
    instance_seed: int | None
    baseline_loss: float
    total_elapsed_wall_seconds: float | None
    records: list[StepRecord]
    completed: bool


def analyze_iterative(
    roots: list[Path],
    *,
    out_dir: Path,
    taus: list[float],
    success_kinds: list[str],
    task_prior_mode: str,
    bootstrap_samples: int,
    bootstrap_seed: int,
    smaller_model: str | None,
    larger_model: str | None,
    pilot_split: str,
    holdout_split: str,
    objective_tolerance_se: float,
) -> dict[str, Any]:
    trajectories = load_trajectories(roots)
    if not trajectories:
        raise ValueError("No iterative trajectories found")
    out_dir.mkdir(parents=True, exist_ok=True)
    max_horizon = max(len(traj.records) for traj in trajectories)
    horizons = list(range(1, max_horizon + 1))

    trajectory_rows = _trajectory_rows(trajectories)
    trajectory_rows.to_csv(out_dir / "trajectory_summary.csv", index=False)

    action_mode_summary, step_metric_summary = _action_routing_summaries(trajectories)
    action_mode_summary.to_csv(out_dir / "action_mode_summary.csv", index=False)
    step_metric_summary.to_csv(out_dir / "step_metric_summary.csv", index=False)

    curves: dict[str, Any] = {}
    for success_kind in success_kinds:
        for tau in taus:
            key = _setting_key(success_kind, tau)
            curves[key] = _compute_curve(
                trajectories,
                horizons=horizons,
                success_kind=success_kind,
                tau=tau,
                task_prior_mode=task_prior_mode,
                smaller_model=smaller_model,
                larger_model=larger_model,
                pilot_split=pilot_split,
                holdout_split=holdout_split,
            )

    bootstrap = _bootstrap_curves(
        trajectories,
        horizons=horizons,
        taus=taus,
        success_kinds=success_kinds,
        task_prior_mode=task_prior_mode,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
        smaller_model=smaller_model,
        larger_model=larger_model,
        pilot_split=pilot_split,
        holdout_split=holdout_split,
    )
    recommendations = _recommend_horizons(curves, bootstrap, tolerance_se=objective_tolerance_se)

    runtime_hours = sum(float(traj.total_elapsed_wall_seconds or 0.0) for traj in trajectories) / 3600.0
    result = {
        "trajectory_count": len(trajectories),
        "observed_runtime_hours": runtime_hours,
        "horizons": horizons,
        "task_modes": sorted({traj.task_mode_true for traj in trajectories}),
        "models": sorted({traj.model_id for traj in trajectories}),
        "taus": taus,
        "success_kinds": success_kinds,
        "task_prior_mode": task_prior_mode,
        "trajectory_rows": trajectory_rows.to_dict(orient="records"),
        "curves": curves,
        "bootstrap": bootstrap,
        "recommended_horizons": recommendations,
    }
    (out_dir / "iterative_analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _plot_objective_curves(curves, recommendations, path=out_dir / "horizon_objectives.png")
    _plot_step_alignment(step_metric_summary, path=out_dir / "step_alignment.png")
    _plot_action_heatmap(action_mode_summary, value_column="top1_rate", title="Top-1 action-mode preference", path=out_dir / "action_preference_heatmap.png")
    _plot_action_heatmap(action_mode_summary, value_column="mean_gain", title="Mean action-mode gain", path=out_dir / "action_gain_heatmap.png")
    _write_report(result, action_mode_summary, step_metric_summary, out_dir / "report.md")
    return result


def load_trajectories(roots: list[Path]) -> list[Trajectory]:
    trajectories: list[Trajectory] = []
    for root in roots:
        for run_dir in iter_run_dirs(root):
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            summary_path = run_dir / "run_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
            task_mode_true = manifest.get("task_mode_true")
            if task_mode_true is None:
                task_mode_true = task_mode_from_instance_overrides(
                    (((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides"))
                )
            if task_mode_true not in TASK_MODE_SET:
                continue
            rows = read_jsonl(run_dir / "evaluations.jsonl")
            records = [StepRecord.model_validate(row) for row in rows]
            if not records:
                continue
            baseline_loss = summary.get("baseline_loss")
            if baseline_loss is None:
                baseline_loss = records[0].parent_latent_loss
            total_elapsed_wall_seconds = summary.get("elapsed_wall_seconds")
            if total_elapsed_wall_seconds is None:
                total_elapsed_wall_seconds = sum(_step_branch_wall_seconds(record) for record in records)
            trajectories.append(
                Trajectory(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or manifest.get("run_id") or run_dir.name),
                    split=str(manifest.get("task_mode_split") or "unspecified"),
                    model_id=str(summary.get("model_id") or manifest.get("model_id")),
                    model_alias=str(manifest.get("model_alias")) if manifest.get("model_alias") else None,
                    task_mode_true=str(task_mode_true),
                    instance_seed=int(manifest["instance_seed"]) if manifest.get("instance_seed") is not None else None,
                    baseline_loss=float(baseline_loss) if baseline_loss is not None else math.inf,
                    total_elapsed_wall_seconds=float(total_elapsed_wall_seconds) if total_elapsed_wall_seconds is not None else None,
                    records=sorted(records, key=lambda record: record.step),
                    completed=summary_path.exists(),
                )
            )
    return trajectories


def _trajectory_rows(trajectories: list[Trajectory]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for traj in trajectories:
        selected_losses = [_selected_branch_loss(record) for record in traj.records]
        best_so_far = []
        running = math.inf
        for loss in selected_losses:
            running = min(running, loss)
            best_so_far.append(running)
        rows.append(
            {
                "run_id": traj.run_id,
                "split": traj.split,
                "task_mode_true": traj.task_mode_true,
                "model_id": traj.model_id,
                "completed": traj.completed,
                "steps_completed": len(traj.records),
                "baseline_loss": traj.baseline_loss,
                "terminal_loss": selected_losses[-1] if selected_losses else math.inf,
                "best_so_far_loss": min(best_so_far) if best_so_far else math.inf,
                "terminal_relative_improvement": _relative_improvement(traj.baseline_loss, selected_losses[-1]) if selected_losses else -math.inf,
                "best_so_far_relative_improvement": _relative_improvement(traj.baseline_loss, min(best_so_far)) if best_so_far else -math.inf,
                "elapsed_wall_seconds": traj.total_elapsed_wall_seconds,
            }
        )
    return pd.DataFrame(rows).sort_values(["split", "task_mode_true", "model_id", "run_id"])


def _action_routing_summaries(trajectories: list[Trajectory]) -> tuple[pd.DataFrame, pd.DataFrame]:
    action_rows: list[dict[str, Any]] = []
    step_rows: list[dict[str, Any]] = []
    for traj in trajectories:
        for record in traj.records:
            gains = gains_by_mode(record)
            productive = max(MODES, key=lambda mode: gains[mode])
            selected_loss = _selected_branch_loss(record)
            step_rows.append(
                {
                    "split": traj.split,
                    "task_mode_true": traj.task_mode_true,
                    "model_id": traj.model_id,
                    "step": record.step + 1,
                    "mean_parent_loss": float(record.parent_latent_loss) if record.parent_latent_loss is not None else math.inf,
                    "selected_loss": selected_loss,
                    "routing_regret": routing_regret(gains, record.selected_mode),
                    "routing_jsd": routing_mismatch_jsd(record),
                    "top1_is_productive": float(record.selected_mode_top1 == productive),
                    "selected_is_productive": float(record.selected_mode == productive),
                }
            )
            for mode in MODES:
                action_rows.append(
                    {
                        "split": traj.split,
                        "task_mode_true": traj.task_mode_true,
                        "model_id": traj.model_id,
                        "step": record.step + 1,
                        "mode": mode,
                        "mode_prob": float(record.mode_probs[mode]),
                        "gain": float(gains[mode]),
                        "top1_rate": float(record.selected_mode_top1 == mode),
                        "selected_rate": float(record.selected_mode == mode),
                        "productive_rate": float(productive == mode),
                    }
                )
    action_frame = pd.DataFrame(action_rows)
    step_frame = pd.DataFrame(step_rows)
    action_summary = (
        action_frame.groupby(["split", "task_mode_true", "model_id", "step", "mode"], as_index=False)
        .agg(
            mean_mode_prob=("mode_prob", "mean"),
            mean_gain=("gain", "mean"),
            median_gain=("gain", "median"),
            top1_rate=("top1_rate", "mean"),
            selected_rate=("selected_rate", "mean"),
            productive_rate=("productive_rate", "mean"),
            count=("gain", "size"),
        )
        .sort_values(["split", "task_mode_true", "model_id", "step", "mode"])
    )
    step_summary = (
        step_frame.groupby(["split", "task_mode_true", "model_id", "step"], as_index=False)
        .agg(
            mean_parent_loss=("mean_parent_loss", "mean"),
            mean_selected_loss=("selected_loss", "mean"),
            mean_routing_regret=("routing_regret", "mean"),
            mean_routing_jsd=("routing_jsd", "mean"),
            top1_productive_rate=("top1_is_productive", "mean"),
            selected_productive_rate=("selected_is_productive", "mean"),
            count=("routing_regret", "size"),
        )
        .sort_values(["split", "task_mode_true", "model_id", "step"])
    )
    return action_summary, step_summary


def _compute_curve(
    trajectories: list[Trajectory],
    *,
    horizons: list[int],
    success_kind: str,
    tau: float,
    task_prior_mode: str,
    smaller_model: str | None,
    larger_model: str | None,
    pilot_split: str,
    holdout_split: str,
) -> dict[str, Any]:
    curve: dict[str, Any] = {}
    for horizon in horizons:
        summary = _prefix_summary_frame(trajectories, horizon=horizon, success_kind=success_kind, tau=tau)
        if summary.empty:
            continue
        summary = _filter_complete_models(summary, pilot_split=pilot_split, holdout_split=holdout_split)
        if summary.empty:
            continue
        priors = _task_mode_priors(summary, split=holdout_split, mode=task_prior_mode)
        pilot_models = summarize_models(summary, split=pilot_split, task_priors=priors)
        if pilot_models.empty:
            continue
        pilot_router = choose_router(summary, split=pilot_split)
        holdout_router = choose_router(summary, split=holdout_split)
        best_single_model = str(pilot_models.iloc[0]["model_id"])
        single_router = {task_mode: {best_single_model: 1.0} for task_mode in priors}
        row: dict[str, Any] = {
            "summary_rows": summary.to_dict(orient="records"),
            "task_mode_priors": priors,
            "single_best_model": best_single_model,
            "pilot_router": pilot_router,
            "oracle_router": holdout_router,
            "pilot_information_gain_nats": mutual_information(priors, pilot_router),
            "holdout_information_gain_nats": mutual_information(priors, holdout_router),
            "pilot_router_mismatch_nats": routing_mismatch(priors, holdout_router, pilot_router),
            "single_model_mismatch_nats": routing_mismatch(priors, holdout_router, single_router),
            "pilot_router_holdout_objective": routing_objective(summary, priors, pilot_router, split=holdout_split),
            "oracle_router_holdout_objective": routing_objective(summary, priors, holdout_router, split=holdout_split),
            "single_best_model_holdout_objective": routing_objective(summary, priors, single_router, split=holdout_split),
            "triviality": {
                "pilot": routing_triviality(summary, split=pilot_split),
                "holdout": routing_triviality(summary, split=holdout_split),
            },
        }
        if smaller_model and larger_model:
            available = set(summary.loc[summary["split"] == holdout_split, "model_id"])
            if smaller_model in available and larger_model in available:
                row["pairwise_terms"] = pairwise_model_terms(
                    summary,
                    split=holdout_split,
                    baseline_model=smaller_model,
                    comparison_model=larger_model,
                    task_priors=priors,
                )
        curve[str(horizon)] = row
    return curve


def _prefix_summary_frame(trajectories: list[Trajectory], *, horizon: int, success_kind: str, tau: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for traj in trajectories:
        if len(traj.records) < horizon:
            continue
        records = traj.records[:horizon]
        terminal_loss = _selected_branch_loss(records[-1])
        best_so_far_loss = min(_selected_branch_loss(record) for record in records)
        terminal_rel = _relative_improvement(traj.baseline_loss, terminal_loss)
        anytime_rel = _relative_improvement(traj.baseline_loss, best_so_far_loss)
        prefix_cost = _allocated_prefix_wall_seconds(traj, horizon=horizon)
        success = terminal_rel >= tau if success_kind == "terminal" else anytime_rel >= tau
        grouped[(traj.split, traj.task_mode_true, traj.model_id)].append(
            {
                "terminal_loss": terminal_loss,
                "best_so_far_loss": best_so_far_loss,
                "terminal_relative_improvement": terminal_rel,
                "anytime_relative_improvement": anytime_rel,
                "prefix_cost": prefix_cost,
                "success": float(success),
                "steps_completed": horizon,
                "baseline_loss": traj.baseline_loss,
            }
        )
    for (split, task_mode, model_id), items in sorted(grouped.items()):
        chosen_losses = [item["terminal_loss"] if success_kind == "terminal" else item["best_so_far_loss"] for item in items]
        rows.append(
            {
                "split": split,
                "task_mode_true": task_mode,
                "model_id": model_id,
                "attempt_count": len(items),
                "success_prob": statistics.fmean(item["success"] for item in items),
                "improvement_prob": statistics.fmean(item["anytime_relative_improvement"] > 0.0 for item in items),
                "mean_relative_improvement": statistics.fmean(item["anytime_relative_improvement"] for item in items),
                "median_relative_improvement": statistics.median(item["anytime_relative_improvement"] for item in items),
                "mean_best_loss": statistics.fmean(chosen_losses),
                "median_best_loss": statistics.median(chosen_losses),
                "mean_baseline_loss": statistics.fmean(item["baseline_loss"] for item in items),
                "mean_counterfactual_gap": None,
                "median_cost": statistics.median(item["prefix_cost"] for item in items),
                "mean_steps_completed": statistics.fmean(item["steps_completed"] for item in items),
            }
        )
    return pd.DataFrame(rows)


def _allocated_prefix_wall_seconds(traj: Trajectory, *, horizon: int) -> float:
    proxies = [_step_branch_wall_seconds(record) for record in traj.records]
    prefix_proxy = sum(proxies[:horizon])
    total_proxy = sum(proxies)
    total_wall = traj.total_elapsed_wall_seconds
    if total_wall is None or not math.isfinite(total_wall) or total_proxy <= 0:
        return prefix_proxy
    return float(total_wall) * prefix_proxy / total_proxy


def _step_branch_wall_seconds(record: StepRecord) -> float:
    return sum(float(branch.elapsed_wall_seconds or 0.0) for branch in record.branches)


def _selected_branch_loss(record: StepRecord) -> float:
    for branch in record.branches:
        if branch.promoted_as_parent or branch.declared_mode == record.selected_mode:
            if branch.correctness and math.isfinite(branch.latent_loss):
                return float(branch.latent_loss)
            return math.inf
    return math.inf


def _relative_improvement(baseline_loss: float, candidate_loss: float) -> float:
    if not math.isfinite(baseline_loss) or baseline_loss <= 0.0 or not math.isfinite(candidate_loss):
        return -math.inf
    return (baseline_loss - candidate_loss) / baseline_loss


def _setting_key(success_kind: str, tau: float) -> str:
    return f"{success_kind}::tau={tau:.3f}"


def _group_trajectories(trajectories: list[Trajectory]) -> dict[tuple[str, str, str], list[Trajectory]]:
    grouped: dict[tuple[str, str, str], list[Trajectory]] = defaultdict(list)
    for traj in trajectories:
        grouped[(traj.split, traj.task_mode_true, traj.model_id)].append(traj)
    return grouped


def _bootstrap_curves(
    trajectories: list[Trajectory],
    *,
    horizons: list[int],
    taus: list[float],
    success_kinds: list[str],
    task_prior_mode: str,
    bootstrap_samples: int,
    bootstrap_seed: int,
    smaller_model: str | None,
    larger_model: str | None,
    pilot_split: str,
    holdout_split: str,
) -> dict[str, Any]:
    grouped = _group_trajectories(trajectories)
    rng = random.Random(bootstrap_seed)
    samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for _ in range(bootstrap_samples):
        sampled: list[Trajectory] = []
        for cell in grouped.values():
            sampled.extend(rng.choices(cell, k=len(cell)))
        for success_kind in success_kinds:
            for tau in taus:
                key = _setting_key(success_kind, tau)
                curve = _compute_curve(
                    sampled,
                    horizons=horizons,
                    success_kind=success_kind,
                    tau=tau,
                    task_prior_mode=task_prior_mode,
                    smaller_model=smaller_model,
                    larger_model=larger_model,
                    pilot_split=pilot_split,
                    holdout_split=holdout_split,
                )
                for horizon in horizons:
                    row = curve.get(str(horizon))
                    if row is None:
                        continue
                    samples[key][f"{horizon}:oracle"].append(float(row["oracle_router_holdout_objective"]))
                    samples[key][f"{horizon}:pilot"].append(float(row["pilot_router_holdout_objective"]))
                    samples[key][f"{horizon}:single"].append(float(row["single_best_model_holdout_objective"]))
    summary: dict[str, Any] = {}
    for setting_key, metrics in samples.items():
        summary[setting_key] = {}
        for metric_key, values in metrics.items():
            series = pd.Series(values, dtype=float)
            summary[setting_key][metric_key] = {
                "mean": float(series.mean()),
                "std": float(series.std(ddof=1)) if len(series) > 1 else 0.0,
                "q025": float(series.quantile(0.025)),
                "q975": float(series.quantile(0.975)),
                "samples": len(values),
            }
    return summary


def _recommend_horizons(curves: dict[str, Any], bootstrap: dict[str, Any], *, tolerance_se: float) -> dict[str, Any]:
    recommendations: dict[str, Any] = {}
    for setting_key, curve in curves.items():
        if not curve:
            continue
        point = {int(horizon): float(values["oracle_router_holdout_objective"]) for horizon, values in curve.items()}
        best_horizon = min(point, key=point.get)
        best_value = point[best_horizon]
        best_std = float(bootstrap.get(setting_key, {}).get(f"{best_horizon}:oracle", {}).get("std", 0.0))
        threshold = best_value + tolerance_se * best_std
        recommended = min(horizon for horizon, value in point.items() if value <= threshold)
        recommendations[setting_key] = {
            "best_horizon": best_horizon,
            "best_oracle_objective": best_value,
            "best_oracle_objective_std": best_std,
            "recommended_horizon": recommended,
            "one_standard_error_threshold": threshold,
        }
    return recommendations


def _plot_objective_curves(curves: dict[str, Any], recommendations: dict[str, Any], *, path: Path) -> None:
    setting_items = [(setting_key, curve) for setting_key, curve in sorted(curves.items()) if curve]
    if not setting_items:
        return
    fig, axes = plt.subplots(len(setting_items), 1, figsize=(8.5, 3.2 * max(1, len(setting_items))), squeeze=False)
    for axis, (setting_key, curve) in zip(axes[:, 0], setting_items):
        horizons = sorted(int(horizon) for horizon in curve)
        axis.plot(horizons, [curve[str(h)]["oracle_router_holdout_objective"] for h in horizons], marker="o", label="oracle")
        axis.plot(horizons, [curve[str(h)]["pilot_router_holdout_objective"] for h in horizons], marker="o", label="pilot")
        axis.plot(horizons, [curve[str(h)]["single_best_model_holdout_objective"] for h in horizons], marker="o", label="single")
        rec = recommendations.get(setting_key)
        if rec:
            axis.axvline(int(rec["recommended_horizon"]), color="#dc2626", linestyle="--", linewidth=1.5)
        axis.set_title(setting_key)
        axis.set_xlabel("horizon")
        axis.set_ylabel("holdout objective")
        axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_step_alignment(step_summary: pd.DataFrame, *, path: Path) -> None:
    if step_summary.empty:
        return
    aggregated = (
        step_summary.groupby(["model_id", "step"], as_index=False)
        .agg(
            mean_routing_regret=("mean_routing_regret", "mean"),
            mean_routing_jsd=("mean_routing_jsd", "mean"),
            top1_productive_rate=("top1_productive_rate", "mean"),
        )
        .sort_values(["model_id", "step"])
    )
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for model_id, frame in aggregated.groupby("model_id"):
        axes[0].plot(frame["step"], frame["mean_routing_regret"], marker="o", label=model_id)
        axes[1].plot(frame["step"], frame["mean_routing_jsd"], marker="o", label=model_id)
        axes[2].plot(frame["step"], frame["top1_productive_rate"], marker="o", label=model_id)
    axes[0].set_title("Routing regret by step")
    axes[1].set_title("Routing JSD by step")
    axes[2].set_title("Top-1 productive rate by step")
    for axis in axes:
        axis.set_xlabel("step")
        axis.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_action_heatmap(action_summary: pd.DataFrame, *, value_column: str, title: str, path: Path) -> None:
    if action_summary.empty:
        return
    aggregated = (
        action_summary.groupby(["split", "task_mode_true", "model_id", "mode"], as_index=False)[value_column]
        .mean()
    )
    aggregated["row"] = aggregated["split"] + " / " + aggregated["task_mode_true"] + " / " + aggregated["model_id"]
    pivot = aggregated.pivot(index="row", columns="mode", values=value_column).fillna(0.0)
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(pivot.index) + 2))
    image = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_report(result: dict[str, Any], action_summary: pd.DataFrame, step_summary: pd.DataFrame, path: Path) -> None:
    completed = int(sum(1 for row in result["trajectory_rows"] if row["completed"]))
    partial = int(result["trajectory_count"] - completed)
    lines = [
        "# Oracle-Family Iterative Analysis",
        "",
        f"- Trajectories: `{result['trajectory_count']}`",
        f"- Completed trajectories: `{completed}`",
        f"- Partial trajectories contributing prefixes: `{partial}`",
        f"- Observed runtime hours: `{result['observed_runtime_hours']:.3f}`",
        f"- Task modes: `{', '.join(result['task_modes'])}`",
        f"- Models: `{', '.join(result['models'])}`",
        f"- Horizons analyzed: `{result['horizons'][0]}..{result['horizons'][-1]}`",
        "",
        "## Recommended Horizons",
        "",
    ]
    for setting_key, rec in sorted(result["recommended_horizons"].items()):
        lines.append(
            f"- `{setting_key}`: recommended horizon=`{rec['recommended_horizon']}`, "
            f"best horizon=`{rec['best_horizon']}`, best oracle objective=`{rec['best_oracle_objective']:.4f}`"
        )
    if not step_summary.empty:
        lines += [
            "",
            "## Action-Routing Highlights",
            "",
        ]
        grouped = (
            action_summary.groupby(["model_id", "mode"], as_index=False)
            .agg(mean_mode_prob=("mean_mode_prob", "mean"), mean_gain=("mean_gain", "mean"))
        )
        for model_id, frame in grouped.groupby("model_id"):
            preferred = frame.sort_values("mean_mode_prob", ascending=False).iloc[0]
            strongest = frame.sort_values("mean_gain", ascending=False).iloc[0]
            lines.append(
                f"- `{model_id}`: highest mean routing mass on `{preferred['mode']}` "
                f"({preferred['mean_mode_prob']:.3f}), strongest mean gain on `{strongest['mode']}` "
                f"({strongest['mean_gain']:.3f})"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--taus", default="0.0,0.05,0.1")
    parser.add_argument("--success-kinds", default="terminal,anytime")
    parser.add_argument("--task-prior-mode", choices=["empirical", "uniform"], default="uniform")
    parser.add_argument("--bootstrap-samples", type=int, default=200)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--smaller-model", default=None)
    parser.add_argument("--larger-model", default=None)
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument("--objective-tolerance-se", type=float, default=1.0)
    args = parser.parse_args(argv)
    result = analyze_iterative(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        taus=[float(item) for item in args.taus.split(",") if item.strip()],
        success_kinds=[item.strip() for item in args.success_kinds.split(",") if item.strip()],
        task_prior_mode=args.task_prior_mode,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        smaller_model=args.smaller_model,
        larger_model=args.larger_model,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        objective_tolerance_se=args.objective_tolerance_se,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
