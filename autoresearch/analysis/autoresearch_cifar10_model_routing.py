"""Summarize task-level model routing on AutoResearch pilot/holdout runs.

This analysis script treats each full AutoResearch trajectory as a run-level
candidate model decision. It estimates per-mode competence/cost on a pilot
split, fits a lightweight mode predictor from router-visible signal features
``Z``, and evaluates best-single-model, learned-router, and oracle-router
policies on a holdout split.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoresearch.benchmark.cifar10.task_spec import TASK_MODE_SET, task_mode_from_instance_overrides
from vao.success_metrics import (
    DEFAULT_SUCCESS_THRESHOLD_RELATIVE,
    relative_improvement,
    success_on_relative_threshold,
    validate_relative_threshold,
)

EPS = 1e-6


@dataclass(frozen=True)
class AttemptRecord:
    run_dir: Path
    run_id: str
    split: str
    model_id: str
    model_alias: str
    task_mode_true: str
    instance_seed: int | None
    baseline_loss: float
    best_loss: float
    relative_improvement: float
    success: bool
    wall_seconds: float | None
    agent_cost_usd: float | None
    total_tokens: int | None
    feature_dict: dict[str, float]


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


def _cost_from_run_dir(run_dir: Path) -> dict[str, float | None]:
    cost_path = run_dir / "cost.json"
    if not cost_path.exists():
        return {"usd": None, "tokens": None}
    payload = json.loads(cost_path.read_text(encoding="utf-8"))
    return {
        "usd": _coerce_float(payload.get("total_cost_usd")),
        "tokens": _coerce_float(payload.get("total_tokens")),
    }


def _infer_model_alias(manifest: dict[str, Any], summary: dict[str, Any], run_dir: Path) -> str:
    alias = manifest.get("model_alias")
    if alias:
        return str(alias)
    include = (((manifest.get("config") or {}).get("models") or {}).get("include") or [])
    if len(include) == 1 and include[0]:
        return str(include[0])
    run_id = str(summary.get("run_id") or manifest.get("run_id") or run_dir.name)
    match = re.search(r"_seed\d+_(.+)$", run_id)
    return match.group(1) if match else str(summary.get("model_id") or manifest.get("model_id") or "unknown_model")


def _extract_program_features(template_path: Path | None) -> dict[str, float]:
    defaults = {
        "depth": 0.0,
        "base_channels": 0.0,
        "dropout_rate": 0.0,
        "learning_rate": 0.0,
        "weight_decay": 0.0,
        "batch_size": 0.0,
        "use_lr_schedule": 0.0,
        "optimizer_is_adam": 0.0,
        "optimizer_is_sgd": 0.0,
    }
    if template_path is None or not template_path.exists():
        return defaults
    text = template_path.read_text(encoding="utf-8")

    def capture_float(name: str) -> float:
        match = re.search(rf"^{name}\s*=\s*([^\n#]+)", text, re.MULTILINE)
        if not match:
            return 0.0
        raw = match.group(1).strip()
        try:
            return float(raw)
        except ValueError:
            return 0.0

    def capture_bool(name: str) -> float:
        match = re.search(rf"^{name}\s*=\s*(True|False)", text, re.MULTILINE)
        if not match:
            return 0.0
        return 1.0 if match.group(1) == "True" else 0.0

    optimizer_match = re.search(r'^OPTIMIZER\s*=\s*"([^"]+)"', text, re.MULTILINE)
    optimizer = optimizer_match.group(1) if optimizer_match else ""
    return {
        "depth": capture_float("DEPTH"),
        "base_channels": capture_float("BASE_CHANNELS"),
        "dropout_rate": capture_float("DROPOUT_RATE"),
        "learning_rate": capture_float("LEARNING_RATE"),
        "weight_decay": capture_float("WEIGHT_DECAY"),
        "batch_size": capture_float("BATCH_SIZE"),
        "use_lr_schedule": capture_bool("USE_LR_SCHEDULE"),
        "optimizer_is_adam": 1.0 if optimizer == "adam" else 0.0,
        "optimizer_is_sgd": 1.0 if optimizer == "sgd" else 0.0,
    }


def _baseline_probe_features(run_dir: Path) -> dict[str, float]:
    metrics_path = run_dir / "verifier_raw" / "baseline" / "artifacts" / "candidate_metrics.json"
    if not metrics_path.exists():
        return {
            "baseline_val_loss": 0.0,
            "baseline_val_accuracy": 0.0,
            "baseline_training_seconds": 0.0,
            "baseline_total_seconds": 0.0,
            "baseline_param_count": 0.0,
            "baseline_total_steps": 0.0,
        }
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "baseline_val_loss": float(metrics.get("val_loss", 0.0)),
        "baseline_val_accuracy": float(metrics.get("val_accuracy", 0.0)),
        "baseline_training_seconds": float(metrics.get("training_seconds", 0.0)),
        "baseline_total_seconds": float(metrics.get("total_seconds", 0.0)),
        "baseline_param_count": float(metrics.get("param_count", 0.0)),
        "baseline_total_steps": float(metrics.get("total_steps", 0.0)),
    }


def _router_visible_features(manifest: dict[str, Any], run_dir: Path, *, feature_set: str) -> dict[str, float]:
    config = manifest.get("config") or {}
    benchmark = config.get("benchmark") or {}
    instance_overrides = benchmark.get("instance_overrides") or {}
    template_path = benchmark.get("template_path")
    metadata_features = {
        "train_subset_size": float(instance_overrides.get("train_subset_size", 0.0)),
        "val_subset_size": float(instance_overrides.get("val_subset_size", 0.0)),
        "label_noise_rate": float(instance_overrides.get("label_noise_rate", 0.0)),
        "imbalance_ratio": float(instance_overrides.get("imbalance_ratio", 1.0)),
        "max_train_steps": float(instance_overrides.get("max_train_steps", 0.0)),
    }
    program_features = _extract_program_features(Path(template_path) if template_path else None)
    probe_features = _baseline_probe_features(run_dir)
    if feature_set == "leaky_current":
        features = dict(metadata_features)
        features.update(program_features)
        features.update(probe_features)
        return features
    if feature_set == "probe_only":
        return probe_features
    if feature_set == "probe_plus_budget":
        return {"max_train_steps": metadata_features["max_train_steps"], **probe_features}
    if feature_set == "budget_only":
        return {"max_train_steps": metadata_features["max_train_steps"]}
    raise ValueError(f"unknown_router_feature_set:{feature_set}")


def _attempt_success(
    *,
    baseline_loss: float,
    best_loss: float,
    improvement_threshold: float,
) -> bool:
    return success_on_relative_threshold(
        baseline_loss,
        best_loss,
        threshold=improvement_threshold,
    )


def load_attempt_records(
    roots: list[Path],
    *,
    improvement_threshold: float | None,
    router_feature_set: str = "probe_only",
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
                task_mode_true = task_mode_from_instance_overrides((((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides")))
            if task_mode_true not in TASK_MODE_SET:
                continue
            baseline_loss = float(summary.get("baseline_loss") or math.inf)
            best_loss = float(summary.get("best_visible_loss") or math.inf)
            relative_improvement_value = relative_improvement(baseline_loss, best_loss)
            threshold_value = validate_relative_threshold(
                improvement_threshold
                if improvement_threshold is not None
                else summary.get("success_threshold_relative", DEFAULT_SUCCESS_THRESHOLD_RELATIVE)
            )
            run_cost = _cost_from_run_dir(run_dir)
            records.append(
                AttemptRecord(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or run_dir.name),
                    split=str(manifest.get("task_mode_split") or "unspecified"),
                    model_id=str(summary.get("model_id") or manifest.get("model_id") or "unknown_model"),
                    model_alias=_infer_model_alias(manifest, summary, run_dir),
                    task_mode_true=str(task_mode_true),
                    instance_seed=_coerce_int(manifest.get("instance_seed")),
                    baseline_loss=baseline_loss,
                    best_loss=best_loss,
                    relative_improvement=relative_improvement_value,
                    success=_attempt_success(
                        baseline_loss=baseline_loss,
                        best_loss=best_loss,
                        improvement_threshold=threshold_value,
                    ),
                    wall_seconds=_coerce_float(summary.get("elapsed_wall_seconds")),
                    agent_cost_usd=run_cost["usd"],
                    total_tokens=_coerce_int(run_cost["tokens"]),
                    feature_dict=_router_visible_features(manifest, run_dir, feature_set=router_feature_set),
                )
            )
    return records


def summarize_attempts(records: list[AttemptRecord], *, cost_metric: str) -> dict[tuple[str, str, str], dict[str, float | str]]:
    grouped: dict[tuple[str, str, str], list[AttemptRecord]] = {}
    for record in records:
        grouped.setdefault((record.split, record.task_mode_true, record.model_alias), []).append(record)
    summary: dict[tuple[str, str, str], dict[str, float | str]] = {}
    for key, items in grouped.items():
        costs = [value for value in (_cost_value(item, cost_metric) for item in items) if value is not None]
        summary[key] = {
            "split": key[0],
            "task_mode_true": key[1],
            "model_alias": key[2],
            "attempt_count": len(items),
            "success_prob": statistics.fmean(1.0 if item.success else 0.0 for item in items),
            "mean_relative_improvement": statistics.fmean(item.relative_improvement for item in items),
            "median_cost": statistics.median(costs) if costs else math.inf,
            "expected_objective": _score_from_items(items, cost_metric=cost_metric),
        }
    return summary


def _cost_value(item: AttemptRecord, cost_metric: str) -> float | None:
    if cost_metric == "wall_seconds":
        return item.wall_seconds
    if cost_metric == "usd":
        return item.agent_cost_usd
    if cost_metric == "tokens":
        return float(item.total_tokens) if item.total_tokens is not None else None
    raise ValueError(f"unknown_cost_metric:{cost_metric}")


def _score_from_items(items: list[AttemptRecord], *, cost_metric: str) -> float:
    p_hat = max(statistics.fmean(1.0 if item.success else 0.0 for item in items), EPS)
    costs = [value for value in (_cost_value(item, cost_metric) for item in items) if value is not None]
    cost = max(statistics.median(costs), EPS) if costs else math.inf
    return -math.log(p_hat) + math.log(cost)


def _task_priors(records: list[AttemptRecord], *, split: str) -> dict[str, float]:
    counts: dict[str, int] = {}
    for record in records:
        if record.split != split:
            continue
        counts[record.task_mode_true] = counts.get(record.task_mode_true, 0) + 1
    total = sum(counts.values())
    return {mode: counts[mode] / total for mode in sorted(counts)} if total else {}


def _mode_scores(summary: dict[tuple[str, str, str], dict[str, float | str]], *, split: str) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, float]] = {}
    for (row_split, mode, model_alias), row in summary.items():
        if row_split != split:
            continue
        scores.setdefault(mode, {})[model_alias] = float(row["expected_objective"])
    return scores


def _best_single_model(summary: dict[tuple[str, str, str], dict[str, float | str]], *, split: str, priors: dict[str, float]) -> tuple[str, float]:
    scores = _mode_scores(summary, split=split)
    models = sorted({model for per_mode in scores.values() for model in per_mode})
    best_model = ""
    best_objective = math.inf
    for model in models:
        total = 0.0
        feasible = True
        for mode, prior in priors.items():
            if model not in scores.get(mode, {}):
                feasible = False
                break
            total += prior * scores[mode][model]
        if feasible and total < best_objective:
            best_objective = total
            best_model = model
    return best_model, best_objective


def _oracle_mode_router(summary: dict[tuple[str, str, str], dict[str, float | str]], *, split: str) -> dict[str, str]:
    scores = _mode_scores(summary, split=split)
    router: dict[str, str] = {}
    for mode, per_model in scores.items():
        router[mode] = min(per_model, key=per_model.get)
    return router


def _feature_order(records: list[AttemptRecord]) -> list[str]:
    names = sorted({name for record in records for name in record.feature_dict})
    return names


def _vectorize(features: dict[str, float], order: list[str]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in order]


def fit_mode_prototypes(records: list[AttemptRecord], *, split: str) -> dict[str, Any]:
    order = _feature_order(records)
    by_mode: dict[str, list[list[float]]] = {}
    for record in records:
        if record.split != split:
            continue
        by_mode.setdefault(record.task_mode_true, []).append(_vectorize(record.feature_dict, order))
    means: dict[str, list[float]] = {}
    scales: list[float] = [1.0 for _ in order]
    all_vectors = [vec for vectors in by_mode.values() for vec in vectors]
    if all_vectors:
        for j in range(len(order)):
            column = [vec[j] for vec in all_vectors]
            scales[j] = max(statistics.pstdev(column), EPS)
    for mode, vectors in by_mode.items():
        means[mode] = [statistics.fmean(vec[j] for vec in vectors) for j in range(len(order))]
    priors = _task_priors(records, split=split)
    return {"feature_order": order, "means": means, "scales": scales, "priors": priors}


def predict_mode_posterior(features: dict[str, float], prototype: dict[str, Any], *, temperature: float = 1.0) -> dict[str, float]:
    order = prototype["feature_order"]
    means = prototype["means"]
    scales = prototype["scales"]
    priors = prototype["priors"]
    x = _vectorize(features, order)
    logits: dict[str, float] = {}
    for mode, mu in means.items():
        distance = 0.0
        for j, value in enumerate(x):
            distance += ((value - mu[j]) / max(scales[j], EPS)) ** 2
        logits[mode] = math.log(max(priors.get(mode, EPS), EPS)) - 0.5 * distance / max(temperature, EPS)
    max_logit = max(logits.values()) if logits else 0.0
    weights = {mode: math.exp(value - max_logit) for mode, value in logits.items()}
    total = sum(weights.values()) or 1.0
    return {mode: weight / total for mode, weight in weights.items()}


def _router_choice_from_posterior(posterior: dict[str, float], mode_scores: dict[str, dict[str, float]]) -> str:
    models = sorted({model for per_mode in mode_scores.values() for model in per_mode})
    best_model = models[0]
    best_score = math.inf
    for model in models:
        total = 0.0
        feasible = True
        for mode, weight in posterior.items():
            if model not in mode_scores.get(mode, {}):
                feasible = False
                break
            total += weight * mode_scores[mode][model]
        if feasible and total < best_score:
            best_score = total
            best_model = model
    return best_model


def _instance_key(record: AttemptRecord) -> tuple[str, str, int | None]:
    return (record.split, record.task_mode_true, record.instance_seed)


def evaluate_holdout(
    records: list[AttemptRecord],
    *,
    pilot_summary: dict[tuple[str, str, str], dict[str, float | str]],
    pilot_split: str,
    holdout_split: str,
    temperature: float,
    cost_metric: str,
) -> dict[str, Any]:
    prototype = fit_mode_prototypes(records, split=pilot_split)
    priors = prototype["priors"]
    mode_scores = _mode_scores(pilot_summary, split=pilot_split)
    oracle_mode_router = _oracle_mode_router(pilot_summary, split=pilot_split)
    best_single_model, best_single_objective = _best_single_model(pilot_summary, split=pilot_split, priors=priors)

    holdout_by_instance: dict[tuple[str, str, int | None], dict[str, AttemptRecord]] = {}
    for record in records:
        if record.split != holdout_split:
            continue
        holdout_by_instance.setdefault(_instance_key(record), {})[record.model_alias] = record

    per_instance: list[dict[str, Any]] = []
    information_terms: list[float] = []
    mismatch_terms: list[float] = []
    learned_objectives: list[float] = []
    oracle_objectives: list[float] = []
    single_objectives: list[float] = []

    for instance_key, model_records in sorted(holdout_by_instance.items()):
        any_record = next(iter(model_records.values()))
        posterior = predict_mode_posterior(any_record.feature_dict, prototype, temperature=temperature)
        learned_model = _router_choice_from_posterior(posterior, mode_scores)
        true_mode = any_record.task_mode_true
        oracle_model = oracle_mode_router[true_mode]
        if learned_model not in model_records or oracle_model not in model_records or best_single_model not in model_records:
            continue
        learned = model_records[learned_model]
        oracle = model_records[oracle_model]
        single = model_records[best_single_model]
        learned_objective = -math.log(max(1.0 if learned.success else EPS, EPS)) + math.log(max(_cost_value(learned, cost_metric) or math.inf, EPS))
        oracle_objective = -math.log(max(1.0 if oracle.success else EPS, EPS)) + math.log(max(_cost_value(oracle, cost_metric) or math.inf, EPS))
        single_objective = -math.log(max(1.0 if single.success else EPS, EPS)) + math.log(max(_cost_value(single, cost_metric) or math.inf, EPS))
        learned_objectives.append(learned_objective)
        oracle_objectives.append(oracle_objective)
        single_objectives.append(single_objective)
        information_terms.append(-sum(weight * math.log(max(weight, EPS)) for weight in posterior.values()))
        mismatch_terms.append(-math.log(max(posterior.get(true_mode, 0.0), EPS)))
        per_instance.append(
            {
                "instance_key": list(instance_key),
                "task_mode_true": true_mode,
                "posterior": posterior,
                "learned_model": learned_model,
                "oracle_model": oracle_model,
                "best_single_model": best_single_model,
                "learned_relative_improvement": learned.relative_improvement,
                "oracle_relative_improvement": oracle.relative_improvement,
                "best_single_relative_improvement": single.relative_improvement,
            }
        )

    prior_entropy = -sum(weight * math.log(max(weight, EPS)) for weight in priors.values())
    conditional_entropy = statistics.fmean(information_terms) if information_terms else math.nan
    return {
        "task_priors": priors,
        "best_single_model": best_single_model,
        "best_single_pilot_objective": best_single_objective,
        "oracle_router": oracle_mode_router,
        "learned_router_avg_objective": statistics.fmean(learned_objectives) if learned_objectives else math.nan,
        "oracle_router_avg_objective": statistics.fmean(oracle_objectives) if oracle_objectives else math.nan,
        "best_single_holdout_objective": statistics.fmean(single_objectives) if single_objectives else math.nan,
        "routing_information": prior_entropy - conditional_entropy if information_terms else math.nan,
        "routing_mismatch_nll": statistics.fmean(mismatch_terms) if mismatch_terms else math.nan,
        "relative_gain_over_best_single": (statistics.fmean(single_objectives) - statistics.fmean(learned_objectives)) if learned_objectives and single_objectives else math.nan,
        "relative_gap_to_oracle": (statistics.fmean(learned_objectives) - statistics.fmean(oracle_objectives)) if learned_objectives and oracle_objectives else math.nan,
        "instance_count": len(per_instance),
        "instances": per_instance,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Run roots containing run_summary.json files")
    parser.add_argument("--output", required=True)
    parser.add_argument("--improvement-threshold", type=float, default=None)
    parser.add_argument("--cost-metric", default="wall_seconds", choices=["wall_seconds", "usd", "tokens"])
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument(
        "--router-feature-set",
        default="probe_only",
        choices=["probe_only", "probe_plus_budget", "budget_only", "leaky_current"],
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    args = parser.parse_args(argv)

    roots = [Path(root) for root in args.roots]
    records = load_attempt_records(
        roots,
        improvement_threshold=args.improvement_threshold,
        router_feature_set=args.router_feature_set,
    )
    summary = summarize_attempts(records, cost_metric=args.cost_metric)
    report = evaluate_holdout(
        records,
        pilot_summary=summary,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        temperature=args.temperature,
        cost_metric=args.cost_metric,
    )
    report["attempt_records"] = len(records)
    report["pilot_summary"] = [
        {
            "split": split,
            "task_mode_true": mode,
            "model_alias": model,
            **row,
        }
        for (split, mode, model), row in sorted(summary.items())
    ]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "instance_count": report["instance_count"]}, indent=2))


if __name__ == "__main__":
    main()
