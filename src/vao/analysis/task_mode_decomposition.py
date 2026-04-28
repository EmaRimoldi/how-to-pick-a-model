"""Estimate oracle-family task-mode decomposition quantities from benchmark runs."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from vao.task_modes import TASK_MODE_SET, task_mode_from_instance_overrides


EPS = 1e-6


@dataclass(frozen=True)
class AttemptRecord:
    run_dir: Path
    run_id: str
    split: str
    model_id: str
    model_alias: str | None
    task_mode_true: str
    instance_seed: int | None
    baseline_loss: float
    best_loss: float
    best_counterfactual_loss: float | None
    relative_improvement: float
    counterfactual_gap: float | None
    success: bool
    wall_seconds: float | None
    agent_cost_usd: float | None
    total_tokens: int | None
    steps_completed: int


def load_attempt_records(
    roots: list[Path],
    *,
    success_threshold: float,
    success_mode: str,
    improvement_threshold: float,
) -> list[AttemptRecord]:
    records: list[AttemptRecord] = []
    for root in roots:
        for summary_path in sorted(root.glob("**/run_summary.json")):
            run_dir = summary_path.parent
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            task_mode_true = manifest.get("task_mode_true")
            if task_mode_true is None:
                task_mode_true = task_mode_from_instance_overrides(
                    (((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides"))
                )
            if task_mode_true not in TASK_MODE_SET:
                continue
            model_alias = _infer_model_alias(manifest, summary, run_dir)
            baseline_loss = summary.get("baseline_loss")
            if baseline_loss is None:
                baseline_loss = math.inf
            baseline_loss = float(baseline_loss)
            best_loss = summary.get("best_visible_loss")
            if best_loss is None:
                best_loss = math.inf
            best_loss = float(best_loss)
            best_counterfactual_loss = summary.get("best_counterfactual_loss")
            if best_counterfactual_loss is not None:
                best_counterfactual_loss = float(best_counterfactual_loss)
            relative_improvement = _relative_improvement(baseline_loss, best_loss)
            counterfactual_gap = None
            if best_counterfactual_loss is not None and math.isfinite(best_counterfactual_loss) and math.isfinite(best_loss):
                counterfactual_gap = best_loss - best_counterfactual_loss
            success = _attempt_success(
                baseline_loss=baseline_loss,
                best_loss=best_loss,
                success_mode=success_mode,
                success_threshold=success_threshold,
                improvement_threshold=improvement_threshold,
            )
            run_cost = _cost_from_run_dir(run_dir)
            records.append(
                AttemptRecord(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or run_dir.name),
                    split=str(manifest.get("task_mode_split") or "unspecified"),
                    model_id=str(summary.get("model_id") or manifest.get("model_id")),
                    model_alias=model_alias,
                    task_mode_true=str(task_mode_true),
                    instance_seed=_coerce_int(manifest.get("instance_seed")),
                    baseline_loss=baseline_loss,
                    best_loss=best_loss,
                    best_counterfactual_loss=best_counterfactual_loss,
                    relative_improvement=relative_improvement,
                    counterfactual_gap=counterfactual_gap,
                    success=success,
                    wall_seconds=_coerce_float(summary.get("elapsed_wall_seconds")),
                    agent_cost_usd=run_cost["usd"],
                    total_tokens=run_cost["tokens"],
                    steps_completed=int(summary.get("steps_completed") or 0),
                )
            )
    return records


def _infer_model_alias(manifest: dict[str, Any], summary: dict[str, Any], run_dir: Path) -> str | None:
    alias = manifest.get("model_alias")
    if alias:
        return str(alias)
    config = manifest.get("config") or {}
    include = ((config.get("models") or {}).get("include") or [])
    if len(include) == 1 and include[0]:
        return str(include[0])
    run_id = str(summary.get("run_id") or manifest.get("run_id") or run_dir.name)
    match = re.search(r"_seed\d+_(.+)$", run_id)
    if match:
        return match.group(1)
    return None


def summarize_attempts(records: list[AttemptRecord], *, cost_metric: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[AttemptRecord]] = {}
    for record in records:
        grouped.setdefault((record.split, record.task_mode_true, record.model_id), []).append(record)
    for (split, task_mode, model_id), items in sorted(grouped.items()):
        cost_values = [_cost_value(item, cost_metric) for item in items if _cost_value(item, cost_metric) is not None]
        relative_improvements = [item.relative_improvement for item in items]
        counterfactual_gaps = [item.counterfactual_gap for item in items if item.counterfactual_gap is not None]
        rows.append(
            {
                "split": split,
                "task_mode_true": task_mode,
                "model_id": model_id,
                "attempt_count": len(items),
                "success_prob": statistics.fmean(item.success for item in items),
                "improvement_prob": statistics.fmean(item.relative_improvement > 0.0 for item in items),
                "mean_relative_improvement": statistics.fmean(relative_improvements),
                "median_relative_improvement": statistics.median(relative_improvements),
                "mean_best_loss": statistics.fmean(item.best_loss for item in items),
                "median_best_loss": statistics.median(item.best_loss for item in items),
                "mean_baseline_loss": statistics.fmean(item.baseline_loss for item in items),
                "mean_counterfactual_gap": statistics.fmean(counterfactual_gaps) if counterfactual_gaps else None,
                "median_cost": statistics.median(cost_values) if cost_values else None,
                "mean_steps_completed": statistics.fmean(item.steps_completed for item in items),
            }
        )
    return pd.DataFrame(rows)


def summarize_models(summary: pd.DataFrame, *, split: str, task_priors: dict[str, float], eps: float = EPS) -> pd.DataFrame:
    subset = summary[summary["split"] == split]
    rows = []
    for model_id in sorted(subset["model_id"].unique()):
        model_rows = subset[subset["model_id"] == model_id]
        if model_rows.empty:
            continue
        rho_total = 0.0
        loss_total = 0.0
        total_weight = 0.0
        for _, row in model_rows.iterrows():
            task_mode = str(row["task_mode_true"])
            if task_mode not in task_priors:
                continue
            weight = float(task_priors[task_mode])
            p_hat = max(float(row["success_prob"]), eps)
            cost = max(float(row["median_cost"]), eps)
            rho_total += weight * (-math.log(p_hat) + math.log(cost))
            loss_total += weight * float(row["mean_best_loss"])
            total_weight += weight
        rows.append(
            {
                "split": split,
                "model_id": model_id,
                "expected_cost_adjusted_nll": rho_total / total_weight if total_weight else math.nan,
                "expected_best_loss": loss_total / total_weight if total_weight else math.nan,
                "median_cost": statistics.median(float(value) for value in model_rows["median_cost"] if pd.notna(value)),
            }
        )
    return pd.DataFrame(rows).sort_values("expected_cost_adjusted_nll")


def choose_router(summary: pd.DataFrame, *, split: str, temperature: float = 0.35, eps: float = EPS) -> dict[str, dict[str, float]]:
    subset = summary[summary["split"] == split]
    router: dict[str, dict[str, float]] = {}
    for task_mode in sorted(subset["task_mode_true"].unique()):
        task_rows = subset[subset["task_mode_true"] == task_mode]
        scores = {}
        for _, row in task_rows.iterrows():
            model_id = str(row["model_id"])
            p_hat = max(float(row["success_prob"]), eps)
            cost = max(float(row["median_cost"]), eps)
            scores[model_id] = -math.log(p_hat) + math.log(cost)
        router[task_mode] = _softmax_scores(scores, temperature=temperature)
    return router


def routing_objective(
    summary: pd.DataFrame,
    task_priors: dict[str, float],
    router: dict[str, dict[str, float]],
    *,
    split: str,
    eps: float = EPS,
) -> float:
    subset = summary[summary["split"] == split]
    lookup = _lookup_table(subset)
    total = 0.0
    for task_mode, prior in task_priors.items():
        q = router.get(task_mode, {})
        for model_id, weight in q.items():
            row = lookup[(task_mode, model_id)]
            p_hat = max(float(row["success_prob"]), eps)
            cost = max(float(row["median_cost"]), eps)
            total += float(prior) * float(weight) * (-math.log(p_hat) + math.log(cost))
    return total


def mutual_information(task_priors: dict[str, float], router: dict[str, dict[str, float]], *, eps: float = EPS) -> float:
    design_marginals: dict[str, float] = {}
    for task_mode, prior in task_priors.items():
        for model_id, weight in router.get(task_mode, {}).items():
            design_marginals[model_id] = design_marginals.get(model_id, 0.0) + float(prior) * float(weight)
    total = 0.0
    for task_mode, prior in task_priors.items():
        for model_id, weight in router.get(task_mode, {}).items():
            if weight <= 0:
                continue
            total += float(prior) * float(weight) * math.log(float(weight) / max(design_marginals[model_id], eps))
    return total


def routing_mismatch(
    task_priors: dict[str, float],
    optimal_router: dict[str, dict[str, float]],
    actual_router: dict[str, dict[str, float]],
    *,
    eps: float = EPS,
) -> float:
    total = 0.0
    for task_mode, prior in task_priors.items():
        optimal = optimal_router.get(task_mode, {})
        actual = actual_router.get(task_mode, {})
        for model_id, optimal_weight in optimal.items():
            if optimal_weight <= 0:
                continue
            total += float(prior) * float(optimal_weight) * math.log(float(optimal_weight) / max(float(actual.get(model_id, 0.0)), eps))
    return total


def routing_triviality(summary: pd.DataFrame, *, split: str, eps: float = EPS) -> dict[str, Any]:
    subset = summary[summary["split"] == split]
    if subset.empty:
        return {}
    lookup = _lookup_table(subset)
    models = sorted(subset["model_id"].unique())
    task_modes = sorted(subset["task_mode_true"].unique())
    model_costs = {model_id: _median_cost_for_model(subset, model_id) for model_id in models}
    best_by_mode: dict[str, str] = {}
    for task_mode in task_modes:
        best_model = min(
            models,
            key=lambda model_id: -math.log(max(float(lookup[(task_mode, model_id)]["success_prob"]), eps))
            + math.log(max(float(model_costs[model_id]), eps)),
        )
        best_by_mode[task_mode] = best_model
    unique_best = sorted(set(best_by_mode.values()))
    delta_cost = max(abs(math.log(max(float(model_costs[left]), eps)) - math.log(max(float(model_costs[right]), eps))) for left in models for right in models)
    delta_comp = max(
        abs(
            math.log(max(float(lookup[(task_mode, left)]["success_prob"]), eps))
            - math.log(max(float(lookup[(task_mode, right)]["success_prob"]), eps))
        )
        for task_mode in task_modes
        for left in models
        for right in models
    )
    return {
        "split": split,
        "task_modes": task_modes,
        "cost_metric_delta": delta_cost,
        "competence_delta": delta_comp,
        "sufficient_condition_fires": delta_comp < delta_cost,
        "routing_is_trivial_empirically": len(unique_best) == 1,
        "best_model_by_task_mode": best_by_mode,
        "unique_best_models": unique_best,
    }


def pairwise_crossover(
    summary: pd.DataFrame,
    *,
    split: str,
    smaller_model: str,
    larger_model: str,
    task_priors: dict[str, float],
    eps: float = EPS,
) -> dict[str, Any]:
    subset = summary[summary["split"] == split]
    lookup = _lookup_table(subset)
    small_cost = _median_cost_for_model(subset, smaller_model)
    large_cost = _median_cost_for_model(subset, larger_model)
    family_rows = []
    for task_mode in sorted(task_priors):
        p_small = max(float(lookup[(task_mode, smaller_model)]["success_prob"]), eps)
        p_large = max(float(lookup[(task_mode, larger_model)]["success_prob"]), eps)
        dcross = _single_mode_crossover(p_small, p_large)
        family_rows.append(
            {
                "task_mode_true": task_mode,
                "success_prob_small": p_small,
                "success_prob_large": p_large,
                "d_cross": dcross,
                "cost_ratio": large_cost / max(small_cost, eps),
                "small_model_dominates_at_equal_cost": dcross <= (large_cost / max(small_cost, eps)),
            }
        )
    aggregate = _aggregate_crossover(family_rows, task_priors)
    return {
        "split": split,
        "smaller_model": smaller_model,
        "larger_model": larger_model,
        "small_cost": small_cost,
        "large_cost": large_cost,
        "cost_ratio": large_cost / max(small_cost, eps),
        "aggregate_d_cross": aggregate,
        "family_rows": family_rows,
    }


def pairwise_model_terms(
    summary: pd.DataFrame,
    *,
    split: str,
    baseline_model: str,
    comparison_model: str,
    task_priors: dict[str, float],
    eps: float = EPS,
) -> dict[str, Any]:
    subset = summary[summary["split"] == split]
    lookup = _lookup_table(subset)
    baseline_cost = _median_cost_for_model(subset, baseline_model)
    comparison_cost = _median_cost_for_model(subset, comparison_model)
    rows: list[dict[str, Any]] = []
    competence_total = 0.0
    for task_mode in sorted(task_priors):
        baseline_success = max(float(lookup[(task_mode, baseline_model)]["success_prob"]), eps)
        comparison_success = max(float(lookup[(task_mode, comparison_model)]["success_prob"]), eps)
        weight = float(task_priors[task_mode])
        contribution = weight * math.log(comparison_success / baseline_success)
        competence_total += contribution
        rows.append(
            {
                "task_mode_true": task_mode,
                "prior": weight,
                "baseline_success_prob": baseline_success,
                "comparison_success_prob": comparison_success,
                "competence_contribution": contribution,
            }
        )
    return {
        "split": split,
        "baseline_model": baseline_model,
        "comparison_model": comparison_model,
        "baseline_cost": baseline_cost,
        "comparison_cost": comparison_cost,
        "cost_term": math.log(max(baseline_cost, eps) / max(comparison_cost, eps)),
        "competence_term": competence_total,
        "per_task_mode": rows,
    }


def analyze(
    roots: list[Path],
    *,
    out_dir: Path,
    success_threshold: float,
    success_mode: str,
    improvement_threshold: float,
    cost_metric: str,
    pilot_split: str,
    holdout_split: str,
    smaller_model: str | None,
    larger_model: str | None,
    task_prior_mode: str,
) -> dict[str, Any]:
    attempts = load_attempt_records(
        roots,
        success_threshold=success_threshold,
        success_mode=success_mode,
        improvement_threshold=improvement_threshold,
    )
    if not attempts:
        raise ValueError("No attempt records found under the provided roots")
    attempts_path = out_dir / "attempt_records.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    attempts_path.write_text(json.dumps([record.__dict__ | {"run_dir": str(record.run_dir)} for record in attempts], indent=2), encoding="utf-8")

    summary = summarize_attempts(attempts, cost_metric=cost_metric)
    summary = _filter_complete_models(summary, pilot_split=pilot_split, holdout_split=holdout_split)
    summary.to_csv(out_dir / "task_mode_model_summary.csv", index=False)

    priors = _task_mode_priors(summary, split=holdout_split, mode=task_prior_mode)
    pilot_models = summarize_models(summary, split=pilot_split, task_priors=priors)
    holdout_models = summarize_models(summary, split=holdout_split, task_priors=priors)
    pilot_models.to_csv(out_dir / "pilot_model_summary.csv", index=False)
    holdout_models.to_csv(out_dir / "holdout_model_summary.csv", index=False)

    pilot_router = choose_router(summary, split=pilot_split)
    holdout_router = choose_router(summary, split=holdout_split)
    pilot_objective = routing_objective(summary, priors, pilot_router, split=holdout_split)
    oracle_objective = routing_objective(summary, priors, holdout_router, split=holdout_split)

    best_single_model = str(pilot_models.iloc[0]["model_id"])
    single_router = {task_mode: {best_single_model: 1.0} for task_mode in priors}
    single_objective = routing_objective(summary, priors, single_router, split=holdout_split)

    triviality = {
        "pilot": routing_triviality(summary, split=pilot_split),
        "holdout": routing_triviality(summary, split=holdout_split),
    }
    decomposition = {
        "pilot_information_gain_nats": mutual_information(priors, pilot_router),
        "holdout_information_gain_nats": mutual_information(priors, holdout_router),
        "pilot_router_mismatch_nats": routing_mismatch(priors, holdout_router, pilot_router),
        "single_model_mismatch_nats": routing_mismatch(priors, holdout_router, single_router),
        "pilot_router_holdout_objective": pilot_objective,
        "oracle_router_holdout_objective": oracle_objective,
        "single_best_model_holdout_objective": single_objective,
        "single_best_model": best_single_model,
        "pilot_router": pilot_router,
        "oracle_router": holdout_router,
    }

    pairwise = None
    pairwise_terms = None
    if smaller_model and larger_model:
        pairwise = pairwise_crossover(
            summary,
            split=holdout_split,
            smaller_model=smaller_model,
            larger_model=larger_model,
            task_priors=priors,
        )
        pairwise_terms = {
            "small_to_large": pairwise_model_terms(
                summary,
                split=holdout_split,
                baseline_model=smaller_model,
                comparison_model=larger_model,
                task_priors=priors,
            ),
            "large_to_small": pairwise_model_terms(
                summary,
                split=holdout_split,
                baseline_model=larger_model,
                comparison_model=smaller_model,
                task_priors=priors,
            ),
        }
        (out_dir / "pairwise_crossover.json").write_text(json.dumps(pairwise, indent=2), encoding="utf-8")
        (out_dir / "pairwise_model_terms.json").write_text(json.dumps(pairwise_terms, indent=2), encoding="utf-8")

    result = {
        "success_threshold": success_threshold,
        "success_mode": success_mode,
        "improvement_threshold": improvement_threshold,
        "cost_metric": cost_metric,
        "task_mode_priors": priors,
        "triviality": triviality,
        "decomposition": decomposition,
        "pairwise_crossover": pairwise,
        "pairwise_model_terms": pairwise_terms,
        "task_prior_mode": task_prior_mode,
    }
    (out_dir / "task_mode_decomposition.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    figures = make_plots(summary, result, out_dir)
    write_report(summary, result, figures, out_dir / "report.md")
    return result


def make_plots(summary: pd.DataFrame, result: dict[str, Any], out_dir: Path) -> dict[str, str]:
    outputs = {
        "success_heatmap": str(out_dir / "success_prob_heatmap.png"),
        "rho_heatmap": str(out_dir / "cost_adjusted_score_heatmap.png"),
        "router_choices": str(out_dir / "router_choice_heatmap.png"),
    }
    _plot_heatmap(summary, split="holdout", value_column="success_prob", path=Path(outputs["success_heatmap"]), title="Holdout success probability by task mode and model")
    _plot_rho_heatmap(summary, split="holdout", path=Path(outputs["rho_heatmap"]))
    _plot_router_choices(result["decomposition"], path=Path(outputs["router_choices"]))
    if result.get("pairwise_crossover"):
        outputs["pairwise_crossover"] = str(out_dir / "pairwise_crossover.png")
        _plot_pairwise_crossover(result["pairwise_crossover"], path=Path(outputs["pairwise_crossover"]))
    return outputs


def write_report(summary: pd.DataFrame, result: dict[str, Any], figures: dict[str, str], path: Path) -> None:
    holdout_models = summary[summary["split"] == "holdout"]
    lines = [
        "# Oracle-Family Task-Mode Decomposition",
        "",
        f"Success mode: `{result['success_mode']}`",
        f"Success threshold: `{result['success_threshold']}`",
        f"Improvement threshold: `{result['improvement_threshold']}`",
        f"Cost metric: `{result['cost_metric']}`",
        f"Task-mode priors: `{result['task_prior_mode']}`",
        "",
        "## Holdout Summary",
        "",
        f"- Single-best pilot model: `{result['decomposition']['single_best_model']}`",
        f"- Single-best holdout objective: `{result['decomposition']['single_best_model_holdout_objective']:.6f}`",
        f"- Pilot router holdout objective: `{result['decomposition']['pilot_router_holdout_objective']:.6f}`",
        f"- Oracle router holdout objective: `{result['decomposition']['oracle_router_holdout_objective']:.6f}`",
        f"- Pilot router information gain (nats): `{result['decomposition']['pilot_information_gain_nats']:.6f}`",
        f"- Pilot router mismatch to oracle (nats): `{result['decomposition']['pilot_router_mismatch_nats']:.6f}`",
        "",
        "## Routing Triviality",
        "",
        f"- Pilot sufficient condition fires: `{result['triviality']['pilot'].get('sufficient_condition_fires')}`",
        f"- Pilot routing trivial empirically: `{result['triviality']['pilot'].get('routing_is_trivial_empirically')}`",
        f"- Holdout routing trivial empirically: `{result['triviality']['holdout'].get('routing_is_trivial_empirically')}`",
        "",
        "## Figures",
        "",
    ]
    for label, figure_path in figures.items():
        lines.append(f"- {label}: `{figure_path}`")
    if result.get("pairwise_crossover"):
        pairwise = result["pairwise_crossover"]
        lines.extend(
            [
                "",
                "## Pairwise Crossover",
                "",
                f"- Smaller model: `{pairwise['smaller_model']}`",
                f"- Larger model: `{pairwise['larger_model']}`",
                f"- Cost ratio: `{pairwise['cost_ratio']:.6f}`",
                f"- Aggregate crossover depth: `{pairwise['aggregate_d_cross']:.6f}`",
            ]
        )
    if result.get("pairwise_model_terms"):
        pairwise_terms = result["pairwise_model_terms"]["small_to_large"]
        lines.extend(
            [
                "",
                "## Pairwise Terms",
                "",
                f"- Baseline model: `{pairwise_terms['baseline_model']}`",
                f"- Comparison model: `{pairwise_terms['comparison_model']}`",
                f"- Cost term: `{pairwise_terms['cost_term']:.6f}`",
                f"- Competence term: `{pairwise_terms['competence_term']:.6f}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--success-threshold", type=float, default=0.95)
    parser.add_argument("--success-mode", choices=["absolute_loss", "relative_improvement"], default="absolute_loss")
    parser.add_argument("--improvement-threshold", type=float, default=0.0)
    parser.add_argument("--cost-metric", choices=["wall_seconds", "tokens", "usd"], default="wall_seconds")
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument("--smaller-model", default=None)
    parser.add_argument("--larger-model", default=None)
    parser.add_argument("--task-prior-mode", choices=["empirical", "uniform"], default="empirical")
    args = parser.parse_args(argv)
    result = analyze(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        success_threshold=args.success_threshold,
        success_mode=args.success_mode,
        improvement_threshold=args.improvement_threshold,
        cost_metric=args.cost_metric,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        smaller_model=args.smaller_model,
        larger_model=args.larger_model,
        task_prior_mode=args.task_prior_mode,
    )
    print(json.dumps(result, indent=2))


def _lookup_table(frame: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    return {
        (str(row["task_mode_true"]), str(row["model_id"])): row
        for _, row in frame.iterrows()
    }


def _filter_complete_models(frame: pd.DataFrame, *, pilot_split: str, holdout_split: str) -> pd.DataFrame:
    required_splits = [pilot_split, holdout_split]
    required_task_modes = set(frame[frame["split"] == holdout_split]["task_mode_true"].unique())
    keep: list[str] = []
    for model_id in sorted(frame["model_id"].unique()):
        model_rows = frame[frame["model_id"] == model_id]
        complete = True
        for split in required_splits:
            split_modes = set(model_rows[model_rows["split"] == split]["task_mode_true"].unique())
            if required_task_modes - split_modes:
                complete = False
                break
        if complete:
            keep.append(str(model_id))
    return frame[frame["model_id"].isin(keep)].copy()


def _median_cost_for_model(frame: pd.DataFrame, model_id: str) -> float:
    values = [float(value) for value in frame[frame["model_id"] == model_id]["median_cost"] if pd.notna(value)]
    if not values:
        return math.inf
    return statistics.median(values)


def _task_mode_priors(frame: pd.DataFrame, *, split: str, mode: str = "empirical") -> dict[str, float]:
    subset = frame[frame["split"] == split]
    task_modes = sorted(str(item) for item in subset["task_mode_true"].unique())
    if not task_modes:
        return {}
    if mode == "uniform":
        weight = 1.0 / len(task_modes)
        return {task_mode: weight for task_mode in task_modes}
    counts = subset.groupby("task_mode_true")["attempt_count"].sum().to_dict()
    total = sum(float(value) for value in counts.values())
    return {str(key): float(value) / total for key, value in counts.items()} if total else {}


def _cost_value(record: AttemptRecord, cost_metric: str) -> float | None:
    if cost_metric == "wall_seconds":
        return record.wall_seconds
    if cost_metric == "tokens":
        return float(record.total_tokens) if record.total_tokens is not None else None
    if cost_metric == "usd":
        return record.agent_cost_usd
    raise ValueError(f"Unsupported cost metric {cost_metric!r}")


def _cost_from_run_dir(run_dir: Path) -> dict[str, float | int | None]:
    evaluations_path = run_dir / "evaluations.jsonl"
    if not evaluations_path.exists():
        return {"usd": None, "tokens": None}
    usd_values: list[float] = []
    token_values: list[int] = []
    for line in evaluations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("agent_cost_usd") is not None:
            usd_values.append(float(payload["agent_cost_usd"]))
        total_tokens = int(payload.get("input_tokens") or 0) + int(payload.get("output_tokens") or 0)
        if total_tokens > 0:
            token_values.append(total_tokens)
    return {
        "usd": statistics.fmean(usd_values) if usd_values else None,
        "tokens": int(statistics.fmean(token_values)) if token_values else None,
    }


def _single_mode_crossover(p_small: float, p_large: float) -> float:
    if p_small <= 0:
        return math.inf
    if p_large >= 1.0:
        return 1.0 if p_small >= 1.0 else math.inf
    if p_large <= p_small:
        return 1.0
    return math.log(1.0 - p_large) / math.log(1.0 - p_small)


def _attempt_success(
    *,
    baseline_loss: float,
    best_loss: float,
    success_mode: str,
    success_threshold: float,
    improvement_threshold: float,
) -> bool:
    if success_mode == "absolute_loss":
        return math.isfinite(best_loss) and best_loss <= float(success_threshold)
    if success_mode == "relative_improvement":
        return _relative_improvement(baseline_loss, best_loss) >= float(improvement_threshold)
    raise ValueError(f"Unsupported success_mode {success_mode!r}")


def _relative_improvement(baseline_loss: float, best_loss: float) -> float:
    if not math.isfinite(baseline_loss) or baseline_loss <= 0.0 or not math.isfinite(best_loss):
        return -math.inf
    return (baseline_loss - best_loss) / baseline_loss


def _aggregate_crossover(rows: list[dict[str, Any]], task_priors: dict[str, float]) -> float:
    def lhs(depth: float) -> float:
        total = 0.0
        for row in rows:
            prior = float(task_priors[row["task_mode_true"]])
            p_small = float(row["success_prob_small"])
            total += prior * (-math.log(max(1.0 - (1.0 - p_small) ** depth, EPS)))
        return total

    rhs = sum(
        float(task_priors[row["task_mode_true"]]) * (-math.log(max(float(row["success_prob_large"]), EPS)))
        for row in rows
    )
    low = 1.0
    high = 64.0
    while lhs(high) > rhs and high < 4096:
        high *= 2.0
    for _ in range(80):
        mid = 0.5 * (low + high)
        if lhs(mid) > rhs:
            low = mid
        else:
            high = mid
    return high


def _softmax_scores(scores: dict[str, float], *, temperature: float) -> dict[str, float]:
    if not scores:
        return {}
    minimum = min(scores.values())
    logits = {key: math.exp(-(value - minimum) / max(temperature, EPS)) for key, value in scores.items()}
    total = sum(logits.values())
    return {key: value / total for key, value in logits.items()}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _plot_heatmap(summary: pd.DataFrame, *, split: str, value_column: str, path: Path, title: str) -> None:
    subset = summary[summary["split"] == split]
    pivot = subset.pivot(index="task_mode_true", columns="model_id", values=value_column)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_title(title)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_rho_heatmap(summary: pd.DataFrame, *, split: str, path: Path) -> None:
    subset = summary[summary["split"] == split].copy()
    subset["rho"] = [
        -math.log(max(float(row["success_prob"]), EPS)) + math.log(max(float(row["median_cost"]), EPS))
        for _, row in subset.iterrows()
    ]
    _plot_heatmap(subset, split=split, value_column="rho", path=path, title="Holdout cost-adjusted score by task mode and model")


def _plot_router_choices(decomposition: dict[str, Any], *, path: Path) -> None:
    pilot_router = decomposition["pilot_router"]
    oracle_router = decomposition["oracle_router"]
    task_modes = sorted(pilot_router)
    model_ids = sorted({model_id for router in [pilot_router, oracle_router] for row in router.values() for model_id in row})
    matrix = []
    for router in [pilot_router, oracle_router]:
        for task_mode in task_modes:
            row = [router.get(task_mode, {}).get(model_id, 0.0) for model_id in model_ids]
            matrix.append(row)
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    image = ax.imshow(np.array(matrix), aspect="auto", cmap="magma")
    ax.set_xticks(range(len(model_ids)), model_ids, rotation=30, ha="right")
    labels = [f"pilot:{task_mode}" for task_mode in task_modes] + [f"oracle:{task_mode}" for task_mode in task_modes]
    ax.set_yticks(range(len(labels)), labels)
    ax.set_title("Pilot and oracle routing distributions by task mode")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_pairwise_crossover(result: dict[str, Any], *, path: Path) -> None:
    rows = result["family_rows"]
    task_modes = [row["task_mode_true"] for row in rows]
    d_cross = [float(row["d_cross"]) for row in rows]
    cost_ratio = float(result["cost_ratio"])
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(task_modes, d_cross, color="#2563eb")
    ax.axhline(cost_ratio, color="#dc2626", linestyle="--", linewidth=2, label="cost ratio")
    ax.set_ylabel("crossover depth")
    ax.set_title(f"Crossover by task mode: {result['smaller_model']} vs {result['larger_model']}")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
