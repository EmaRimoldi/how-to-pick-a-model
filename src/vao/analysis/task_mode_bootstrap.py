"""Bootstrap confidence intervals for oracle-family decomposition terms."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from vao.analysis.task_mode_decomposition import (
    AttemptRecord,
    _filter_complete_models,
    _task_mode_priors,
    choose_router,
    load_attempt_records,
    mutual_information,
    pairwise_model_terms,
    routing_mismatch,
    routing_objective,
    routing_triviality,
    summarize_attempts,
    summarize_models,
)


def bootstrap_decomposition(
    roots: list[Path],
    *,
    out_dir: Path,
    success_threshold: float,
    success_mode: str,
    improvement_threshold: float,
    pilot_split: str,
    holdout_split: str,
    smaller_model: str | None,
    larger_model: str | None,
    cost_metric: str,
    bootstrap_samples: int,
    random_seed: int,
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

    out_dir.mkdir(parents=True, exist_ok=True)
    point = _compute_metrics(
        attempts,
        pilot_split=pilot_split,
        holdout_split=holdout_split,
        smaller_model=smaller_model,
        larger_model=larger_model,
        cost_metric=cost_metric,
        task_prior_mode=task_prior_mode,
    )
    grouped = _group_attempts(attempts)
    rng = random.Random(random_seed)
    samples: list[dict[str, Any]] = []
    for _ in range(bootstrap_samples):
        sampled_attempts: list[AttemptRecord] = []
        for cell_attempts in grouped.values():
            sampled_attempts.extend(rng.choices(cell_attempts, k=len(cell_attempts)))
        samples.append(
            _compute_metrics(
                sampled_attempts,
                pilot_split=pilot_split,
                holdout_split=holdout_split,
                smaller_model=smaller_model,
                larger_model=larger_model,
                cost_metric=cost_metric,
                task_prior_mode=task_prior_mode,
            )
        )

    summary = _summarize_bootstrap(samples, point)
    result = {
        "success_threshold": success_threshold,
        "success_mode": success_mode,
        "improvement_threshold": improvement_threshold,
        "cost_metric": cost_metric,
        "bootstrap_samples": bootstrap_samples,
        "random_seed": random_seed,
        "task_prior_mode": task_prior_mode,
        "point_estimate": point,
        "bootstrap_summary": summary,
    }
    (out_dir / "task_mode_bootstrap.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "bootstrap_draws.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    _write_report(result, out_dir / "report.md")
    return result


def _group_attempts(attempts: list[AttemptRecord]) -> dict[tuple[str, str, str], list[AttemptRecord]]:
    grouped: dict[tuple[str, str, str], list[AttemptRecord]] = defaultdict(list)
    for attempt in attempts:
        grouped[(attempt.split, attempt.task_mode_true, attempt.model_id)].append(attempt)
    return grouped


def _compute_metrics(
    attempts: list[AttemptRecord],
    *,
    pilot_split: str,
    holdout_split: str,
    smaller_model: str | None,
    larger_model: str | None,
    cost_metric: str,
    task_prior_mode: str,
) -> dict[str, Any]:
    summary = summarize_attempts(attempts, cost_metric=cost_metric)
    summary = _filter_complete_models(summary, pilot_split=pilot_split, holdout_split=holdout_split)
    priors = _task_mode_priors(summary, split=holdout_split, mode=task_prior_mode)
    pilot_router = choose_router(summary, split=pilot_split)
    holdout_router = choose_router(summary, split=holdout_split)
    pilot_models = summarize_models(summary, split=pilot_split, task_priors=priors)
    best_single_model = str(pilot_models.iloc[0]["model_id"])
    single_router = {task_mode: {best_single_model: 1.0} for task_mode in priors}
    decomposition = {
        "pilot_information_gain_nats": mutual_information(priors, pilot_router),
        "holdout_information_gain_nats": mutual_information(priors, holdout_router),
        "pilot_router_mismatch_nats": routing_mismatch(priors, holdout_router, pilot_router),
        "single_model_mismatch_nats": routing_mismatch(priors, holdout_router, single_router),
        "pilot_router_holdout_objective": routing_objective(summary, priors, pilot_router, split=holdout_split),
        "oracle_router_holdout_objective": routing_objective(summary, priors, holdout_router, split=holdout_split),
        "single_best_model_holdout_objective": routing_objective(summary, priors, single_router, split=holdout_split),
        "single_best_model": best_single_model,
    }
    triviality = {
        "pilot": routing_triviality(summary, split=pilot_split),
        "holdout": routing_triviality(summary, split=holdout_split),
    }
    pairwise = None
    if smaller_model and larger_model:
        small_to_large = pairwise_model_terms(
            summary,
            split=holdout_split,
            baseline_model=smaller_model,
            comparison_model=larger_model,
            task_priors=priors,
        )
        pairwise = {
            "baseline_model": smaller_model,
            "comparison_model": larger_model,
            "cost_term": float(small_to_large["cost_term"]),
            "competence_term": float(small_to_large["competence_term"]),
            "per_task_mode": small_to_large["per_task_mode"],
        }
    cell_success = {
        f"{row['split']}::{row['task_mode_true']}::{row['model_id']}": float(row["success_prob"])
        for _, row in summary.iterrows()
    }
    return {
        "decomposition": decomposition,
        "triviality": triviality,
        "pairwise_terms": pairwise,
        "cell_success": cell_success,
    }


def _summarize_bootstrap(samples: list[dict[str, Any]], point: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, list[float]] = defaultdict(list)
    categorical: dict[str, list[str]] = defaultdict(list)
    booleans: dict[str, list[bool]] = defaultdict(list)
    for sample in samples:
        decomp = sample["decomposition"]
        for key, value in decomp.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                metrics[f"decomposition.{key}"].append(float(value))
            elif isinstance(value, str):
                categorical[f"decomposition.{key}"].append(value)
        for split in ["pilot", "holdout"]:
            triv = sample["triviality"][split]
            if triv:
                booleans[f"triviality.{split}.sufficient_condition_fires"].append(bool(triv.get("sufficient_condition_fires")))
                booleans[f"triviality.{split}.routing_is_trivial_empirically"].append(bool(triv.get("routing_is_trivial_empirically")))
                categorical[f"triviality.{split}.best_range_local_scans"].append(str(triv.get("best_model_by_task_mode", {}).get("range_local_scans")))
                categorical[f"triviality.{split}.best_topk_stress"].append(str(triv.get("best_model_by_task_mode", {}).get("topk_stress")))
        pairwise = sample.get("pairwise_terms")
        if pairwise:
            for key in ["cost_term", "competence_term"]:
                value = pairwise.get(key)
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    metrics[f"pairwise.{key}"].append(float(value))
            for row in pairwise.get("per_task_mode", []):
                task_mode = str(row["task_mode_true"])
                value = row.get("comparison_success_prob")
                base = row.get("baseline_success_prob")
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    metrics[f"pairwise.success_prob_comparison.{task_mode}"].append(float(value))
                if isinstance(base, (int, float)) and math.isfinite(float(base)):
                    metrics[f"pairwise.success_prob_baseline.{task_mode}"].append(float(base))
        for key, value in sample.get("cell_success", {}).items():
            if math.isfinite(float(value)):
                metrics[f"cell_success.{key}"].append(float(value))

    numeric_summary = {
        key: _quantile_summary(values, point_value=_lookup_point(point, key))
        for key, values in metrics.items()
    }
    boolean_summary = {
        key: {
            "point_estimate": bool(_lookup_point(point, key)),
            "bootstrap_mean": sum(values) / len(values) if values else math.nan,
            "bootstrap_probability_true": sum(values) / len(values) if values else math.nan,
            "samples": len(values),
        }
        for key, values in booleans.items()
    }
    categorical_summary = {
        key: {
            "point_estimate": _lookup_point(point, key),
            "bootstrap_mode": _mode(values),
            "bootstrap_agreement": _agreement(values),
            "samples": len(values),
        }
        for key, values in categorical.items()
    }
    return {
        "numeric": numeric_summary,
        "boolean": boolean_summary,
        "categorical": categorical_summary,
    }


def _quantile_summary(values: list[float], *, point_value: Any) -> dict[str, Any]:
    series = pd.Series(values)
    return {
        "point_estimate": point_value,
        "mean": float(series.mean()),
        "std": float(series.std(ddof=1)) if len(series) > 1 else 0.0,
        "q025": float(series.quantile(0.025)),
        "q50": float(series.quantile(0.5)),
        "q975": float(series.quantile(0.975)),
        "samples": len(values),
    }


def _mode(values: list[str]) -> str | None:
    if not values:
        return None
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return max(sorted(counts), key=lambda item: counts[item])


def _agreement(values: list[str]) -> float:
    if not values:
        return math.nan
    mode = _mode(values)
    assert mode is not None
    return sum(value == mode for value in values) / len(values)


def _lookup_point(point: dict[str, Any], key: str) -> Any:
    current: Any = point
    for part in key.split("."):
        if isinstance(current, dict):
            if part == "pairwise" and "pairwise_terms" in current:
                current = current.get("pairwise_terms")
                continue
            current = current.get(part)
        else:
            return None
    return current


def _write_report(result: dict[str, Any], path: Path) -> None:
    numeric = result["bootstrap_summary"]["numeric"]
    boolean = result["bootstrap_summary"]["boolean"]
    lines = [
        "# Task-Mode Bootstrap",
        "",
        f"- Success mode: `{result['success_mode']}`",
        f"- Success threshold: `{result['success_threshold']}`",
        f"- Improvement threshold: `{result['improvement_threshold']}`",
        f"- Bootstrap samples: `{result['bootstrap_samples']}`",
        f"- Task-mode priors: `{result['task_prior_mode']}`",
        "",
        "## Key Numeric Terms",
        "",
    ]
    for key in [
        "pairwise.cost_term",
        "pairwise.competence_term",
        "decomposition.pilot_information_gain_nats",
        "decomposition.holdout_information_gain_nats",
        "decomposition.pilot_router_mismatch_nats",
        "decomposition.single_model_mismatch_nats",
        "decomposition.pilot_router_holdout_objective",
        "decomposition.oracle_router_holdout_objective",
        "decomposition.single_best_model_holdout_objective",
    ]:
        if key not in numeric:
            continue
        row = numeric[key]
        lines.append(
            f"- `{key}`: point=`{row['point_estimate']:.6f}`, "
            f"95% bootstrap CI=`[{row['q025']:.6f}, {row['q975']:.6f}]`"
        )
    lines += [
        "",
        "## Key Boolean Terms",
        "",
    ]
    for key in [
        "triviality.pilot.sufficient_condition_fires",
        "triviality.pilot.routing_is_trivial_empirically",
        "triviality.holdout.sufficient_condition_fires",
        "triviality.holdout.routing_is_trivial_empirically",
    ]:
        if key not in boolean:
            continue
        row = boolean[key]
        lines.append(
            f"- `{key}`: point=`{row['point_estimate']}`, "
            f"bootstrap true-rate=`{row['bootstrap_probability_true']:.3f}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--success-threshold", type=float, default=0.95)
    parser.add_argument("--success-mode", choices=["absolute_loss", "relative_improvement"], default="relative_improvement")
    parser.add_argument("--improvement-threshold", type=float, default=0.05)
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument("--smaller-model", default=None)
    parser.add_argument("--larger-model", default=None)
    parser.add_argument("--cost-metric", choices=["wall_seconds", "agent_cost_usd", "tokens"], default="wall_seconds")
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--task-prior-mode", choices=["empirical", "uniform"], default="empirical")
    args = parser.parse_args(argv)
    result = bootstrap_decomposition(
        [Path(item) for item in args.runs],
        out_dir=Path(args.out_dir),
        success_threshold=args.success_threshold,
        success_mode=args.success_mode,
        improvement_threshold=args.improvement_threshold,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        smaller_model=args.smaller_model,
        larger_model=args.larger_model,
        cost_metric=args.cost_metric,
        bootstrap_samples=args.bootstrap_samples,
        random_seed=args.seed,
        task_prior_mode=args.task_prior_mode,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
