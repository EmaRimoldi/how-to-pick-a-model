"""Decision-theoretic accounting for AutoResearch workload routing.

This analysis is aligned with the revised paper framing:
- best single model baseline
- workload-conditioned deployment policy
- workload + cheap-probe learned router
- per-instance oracle

The benchmark is treated as a single AutoResearch meta-task instantiated on a
small family of realistic workloads.
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
from vao.taxonomy import MODES

EPS = 1e-6


@dataclass(frozen=True)
class AttemptRecord:
    run_dir: Path
    run_id: str
    split: str
    model_alias: str
    workload_id: str
    instance_seed: int | None
    baseline_loss: float
    best_loss: float
    relative_improvement: float
    success: bool
    wall_seconds: float | None
    agent_cost_usd: float | None
    total_tokens: int | None
    feature_dict: dict[str, float]


@dataclass(frozen=True)
class InstanceBundle:
    split: str
    workload_id: str
    instance_seed: int | None
    feature_dict: dict[str, float]
    attempts: dict[str, AttemptRecord]


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
    return match.group(1) if match else "unknown_model"


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
        try:
            return float(match.group(1).strip())
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


def _split_from_manifest(manifest: dict[str, Any]) -> str:
    return str(manifest.get("task_mode_split") or manifest.get("workload_split") or "unspecified")


def _workload_from_manifest(manifest: dict[str, Any]) -> str | None:
    workload_id = manifest.get("task_mode_true")
    if workload_id is None:
        workload_id = task_mode_from_instance_overrides((((manifest.get("config") or {}).get("benchmark") or {}).get("instance_overrides")))
    if workload_id not in TASK_MODE_SET:
        return None
    return str(workload_id)


def _instance_key(*, split: str, workload_id: str, instance_seed: int | None) -> tuple[str, str, int | None]:
    return (str(split), str(workload_id), instance_seed)


def _safe_feature_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_probe_feature_index(roots: list[Path]) -> dict[tuple[str, str, int | None], dict[str, float]]:
    index: dict[tuple[str, str, int | None], dict[str, float]] = {}
    for root in roots:
        for summary_path in sorted(root.glob("**/run_summary.json")):
            run_dir = summary_path.parent
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.exists():
                continue
            manifest = _load_json(manifest_path)
            workload_id = _workload_from_manifest(manifest)
            if workload_id is None:
                continue
            summary = _load_json(summary_path)
            split = _split_from_manifest(manifest)
            instance_seed = _coerce_int(manifest.get("instance_seed"))
            key = _instance_key(split=split, workload_id=workload_id, instance_seed=instance_seed)

            model_alias = _safe_feature_token(_infer_model_alias(manifest, summary, run_dir))
            steps_completed = int(summary.get("steps_completed") or 0)
            prefix = f"probe_{model_alias}_s{steps_completed}"
            feature_dict: dict[str, float] = {
                f"{prefix}_baseline_loss": float(summary.get("baseline_loss") or 0.0),
                f"{prefix}_best_visible_loss": float(summary.get("best_visible_loss") or 0.0),
                f"{prefix}_best_visible_relative_improvement": float(summary.get("best_visible_relative_improvement") or 0.0),
                f"{prefix}_elapsed_wall_seconds": float(summary.get("elapsed_wall_seconds") or 0.0),
                f"{prefix}_branch_evaluations": float(summary.get("branch_evaluations") or 0.0),
                f"{prefix}_success": 1.0 if summary.get("success") else 0.0,
                f"{prefix}_tau_step": float(summary.get("tau_step") or 0.0),
            }

            step0_path = run_dir / "steps" / "step_0000" / "step_record.json"
            if step0_path.exists():
                step0 = _load_json(step0_path)
                selected_mode = str(step0.get("selected_mode") or "unknown")
                for mode in MODES:
                    feature_dict[f"{prefix}_step0_selected_is_{mode}"] = 1.0 if selected_mode == mode else 0.0
                mode_probs = step0.get("mode_probs") or {}
                entropy = 0.0
                for mode in MODES:
                    prob = float(mode_probs.get(mode, 0.0))
                    feature_dict[f"{prefix}_step0_prob_{mode}"] = prob
                    if prob > 0:
                        entropy -= prob * math.log(max(prob, EPS))
                feature_dict[f"{prefix}_step0_entropy"] = entropy

            index.setdefault(key, {}).update(feature_dict)
    return index


def _router_visible_features(
    manifest: dict[str, Any],
    run_dir: Path,
    *,
    feature_set: str,
    external_probe_features: dict[str, float] | None = None,
) -> dict[str, float]:
    config = manifest.get("config") or {}
    benchmark = config.get("benchmark") or {}
    instance_overrides = benchmark.get("instance_overrides") or {}
    template_path = benchmark.get("template_path")
    workload_id = manifest.get("task_mode_true") or task_mode_from_instance_overrides(instance_overrides) or "unknown"
    workload_one_hot = {f"workload_is_{key}": 1.0 if key == workload_id else 0.0 for key in sorted(TASK_MODE_SET)}
    metadata_features = {
        "train_subset_size": float(instance_overrides.get("train_subset_size", 0.0)),
        "val_subset_size": float(instance_overrides.get("val_subset_size", 0.0)),
        "label_noise_rate": float(instance_overrides.get("label_noise_rate", 0.0)),
        "imbalance_ratio": float(instance_overrides.get("imbalance_ratio", 1.0)),
        "max_train_steps": float(instance_overrides.get("max_train_steps", 0.0)),
    }
    program_features = _extract_program_features(Path(template_path) if template_path else None)
    probe_features = _baseline_probe_features(run_dir)
    if feature_set == "probe_only":
        return probe_features
    if feature_set == "workload_only":
        features = dict(workload_one_hot)
        features.update(metadata_features)
        features.update(program_features)
        return features
    if feature_set == "workload_plus_probe":
        features = _router_visible_features(manifest, run_dir, feature_set="workload_only")
        features.update(probe_features)
        return features
    if feature_set == "shortprobe_only":
        return dict(external_probe_features or {})
    if feature_set == "workload_plus_shortprobe":
        features = _router_visible_features(manifest, run_dir, feature_set="workload_only")
        features.update(external_probe_features or {})
        return features
    if feature_set == "workload_plus_interactions":
        features = _router_visible_features(manifest, run_dir, feature_set="workload_plus_probe")
        features.update(external_probe_features or {})
        return features
    if feature_set == "leaky_current":
        features = _router_visible_features(manifest, run_dir, feature_set="workload_plus_probe")
        return features
    raise ValueError(f"unknown_router_feature_set:{feature_set}")


def _attempt_success(*, baseline_loss: float, best_loss: float, improvement_threshold: float) -> bool:
    return success_on_relative_threshold(baseline_loss, best_loss, threshold=improvement_threshold)


def load_attempt_records(
    roots: list[Path],
    *,
    improvement_threshold: float | None,
    router_feature_set: str,
    probe_feature_index: dict[tuple[str, str, int | None], dict[str, float]] | None = None,
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
            workload_id = _workload_from_manifest(manifest)
            if workload_id is None:
                continue
            split = _split_from_manifest(manifest)
            instance_seed = _coerce_int(manifest.get("instance_seed"))
            extra_probe_features = {}
            if probe_feature_index is not None:
                extra_probe_features = probe_feature_index.get(
                    _instance_key(split=split, workload_id=workload_id, instance_seed=instance_seed),
                    {},
                )
            baseline_loss = float(summary.get("baseline_loss") or math.inf)
            best_loss = float(summary.get("best_visible_loss") or math.inf)
            relative_improvement_value = relative_improvement(baseline_loss, best_loss)
            threshold_value = validate_relative_threshold(
                improvement_threshold if improvement_threshold is not None else summary.get("success_threshold_relative", DEFAULT_SUCCESS_THRESHOLD_RELATIVE)
            )
            run_cost = _cost_from_run_dir(run_dir)
            records.append(
                AttemptRecord(
                    run_dir=run_dir,
                    run_id=str(summary.get("run_id") or run_dir.name),
                    split=split,
                    model_alias=_infer_model_alias(manifest, summary, run_dir),
                    workload_id=str(workload_id),
                    instance_seed=instance_seed,
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
                    feature_dict=_router_visible_features(
                        manifest,
                        run_dir,
                        feature_set=router_feature_set,
                        external_probe_features=extra_probe_features,
                    ),
                )
            )
    return records


def _cost_value(item: AttemptRecord, cost_metric: str) -> float | None:
    if cost_metric == "wall_seconds":
        return item.wall_seconds
    if cost_metric == "usd":
        return item.agent_cost_usd
    if cost_metric == "tokens":
        return float(item.total_tokens) if item.total_tokens is not None else None
    raise ValueError(f"unknown_cost_metric:{cost_metric}")


def _objective(item: AttemptRecord, *, cost_metric: str) -> float:
    p = 1.0 if item.success else EPS
    cost = _cost_value(item, cost_metric) or math.inf
    return -math.log(max(p, EPS)) + math.log(max(cost, EPS))


def build_instance_bundles(records: list[AttemptRecord]) -> list[InstanceBundle]:
    grouped: dict[tuple[str, str, int | None], dict[str, AttemptRecord]] = {}
    feature_index: dict[tuple[str, str, int | None], dict[str, float]] = {}
    for record in records:
        key = (record.split, record.workload_id, record.instance_seed)
        grouped.setdefault(key, {})[record.model_alias] = record
        feature_index[key] = dict(record.feature_dict)
    bundles: list[InstanceBundle] = []
    for (split, workload_id, instance_seed), attempts in sorted(grouped.items()):
        bundles.append(
            InstanceBundle(
                split=split,
                workload_id=workload_id,
                instance_seed=instance_seed,
                feature_dict=feature_index[(split, workload_id, instance_seed)],
                attempts=attempts,
            )
        )
    return bundles


def summarize_workload_matrix(bundles: list[InstanceBundle], *, split: str, cost_metric: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, list[float]]] = {}
    for bundle in bundles:
        if bundle.split != split:
            continue
        grouped.setdefault(bundle.workload_id, {})
        for model_alias, record in bundle.attempts.items():
            grouped[bundle.workload_id].setdefault(model_alias, []).append(_objective(record, cost_metric=cost_metric))
    return {
        workload_id: {
            model_alias: statistics.fmean(values)
            for model_alias, values in per_model.items()
            if values
        }
        for workload_id, per_model in grouped.items()
    }


def best_single_model(bundles: list[InstanceBundle], *, split: str, cost_metric: str) -> tuple[str, float]:
    per_model: dict[str, list[float]] = {}
    for bundle in bundles:
        if bundle.split != split:
            continue
        for model_alias, record in bundle.attempts.items():
            per_model.setdefault(model_alias, []).append(_objective(record, cost_metric=cost_metric))
    best_model = ""
    best_score = math.inf
    for model_alias, values in sorted(per_model.items()):
        score = statistics.fmean(values)
        if score < best_score:
            best_score = score
            best_model = model_alias
    return best_model, best_score


def workload_policy(matrix: dict[str, dict[str, float]]) -> dict[str, str]:
    return {workload_id: min(per_model, key=per_model.get) for workload_id, per_model in matrix.items() if per_model}


def _feature_order_for_workload(bundles: list[InstanceBundle], *, workload_id: str) -> list[str]:
    names = set()
    for bundle in bundles:
        if bundle.workload_id == workload_id:
            names.update(bundle.feature_dict)
    return sorted(names)


def _vectorize(features: dict[str, float], order: list[str]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in order]


def _standardization(vectors: list[list[float]]) -> tuple[list[float], list[float]]:
    if not vectors:
        return [], []
    dims = len(vectors[0])
    means = [statistics.fmean(vec[j] for vec in vectors) for j in range(dims)]
    scales = []
    for j in range(dims):
        column = [vec[j] for vec in vectors]
        scales.append(max(statistics.pstdev(column), EPS))
    return means, scales


def _distance(x: list[float], y: list[float], means: list[float], scales: list[float]) -> float:
    total = 0.0
    for j, value in enumerate(x):
        total += (((value - means[j]) - (y[j] - means[j])) / max(scales[j], EPS)) ** 2
    return total


def predict_model_for_bundle(
    bundle: InstanceBundle,
    pilot_bundles: list[InstanceBundle],
    *,
    cost_metric: str,
    k: int,
) -> str:
    candidates = [item for item in pilot_bundles if item.workload_id == bundle.workload_id]
    if not candidates:
        return min(bundle.attempts, key=lambda model_alias: _objective(bundle.attempts[model_alias], cost_metric=cost_metric))
    order = _feature_order_for_workload(candidates + [bundle], workload_id=bundle.workload_id)
    pilot_vectors = [_vectorize(item.feature_dict, order) for item in candidates]
    means, scales = _standardization(pilot_vectors)
    query = _vectorize(bundle.feature_dict, order)
    ranked = sorted(
        ((item, _distance(query, _vectorize(item.feature_dict, order), means, scales)) for item in candidates),
        key=lambda pair: pair[1],
    )
    neighbors = ranked[: max(k, 1)]
    predictions: dict[str, list[float]] = {}
    for neighbor, dist in neighbors:
        weight = 1.0 / max(dist, 1e-4)
        for model_alias, record in neighbor.attempts.items():
            predictions.setdefault(model_alias, []).append(weight * _objective(record, cost_metric=cost_metric))
    scored = {model_alias: sum(values) / len(values) for model_alias, values in predictions.items() if values}
    return min(scored, key=scored.get)


def evaluate_accounting(
    bundles: list[InstanceBundle],
    *,
    pilot_split: str,
    holdout_split: str,
    cost_metric: str,
    knn_k: int,
) -> dict[str, Any]:
    pilot_bundles = [bundle for bundle in bundles if bundle.split == pilot_split]
    holdout_bundles = [bundle for bundle in bundles if bundle.split == holdout_split]
    matrix = summarize_workload_matrix(bundles, split=pilot_split, cost_metric=cost_metric)
    single_model, single_score = best_single_model(bundles, split=pilot_split, cost_metric=cost_metric)
    workload_router = workload_policy(matrix)

    per_instance: list[dict[str, Any]] = []
    best_single_objectives: list[float] = []
    workload_objectives: list[float] = []
    learned_objectives: list[float] = []
    oracle_objectives: list[float] = []

    for bundle in holdout_bundles:
        if single_model not in bundle.attempts or bundle.workload_id not in workload_router:
            continue
        best_single_record = bundle.attempts[single_model]
        workload_record = bundle.attempts[workload_router[bundle.workload_id]]
        oracle_model = min(bundle.attempts, key=lambda model_alias: _objective(bundle.attempts[model_alias], cost_metric=cost_metric))
        oracle_record = bundle.attempts[oracle_model]
        learned_model = predict_model_for_bundle(bundle, pilot_bundles, cost_metric=cost_metric, k=knn_k)
        if learned_model not in bundle.attempts:
            learned_model = workload_router[bundle.workload_id]
        learned_record = bundle.attempts[learned_model]

        obj_single = _objective(best_single_record, cost_metric=cost_metric)
        obj_workload = _objective(workload_record, cost_metric=cost_metric)
        obj_learned = _objective(learned_record, cost_metric=cost_metric)
        obj_oracle = _objective(oracle_record, cost_metric=cost_metric)
        best_single_objectives.append(obj_single)
        workload_objectives.append(obj_workload)
        learned_objectives.append(obj_learned)
        oracle_objectives.append(obj_oracle)
        per_instance.append(
            {
                "split": bundle.split,
                "workload_id": bundle.workload_id,
                "instance_seed": bundle.instance_seed,
                "best_single_model": single_model,
                "workload_model": workload_router[bundle.workload_id],
                "learned_model": learned_model,
                "oracle_model": oracle_model,
                "best_single_objective": obj_single,
                "workload_objective": obj_workload,
                "learned_objective": obj_learned,
                "oracle_objective": obj_oracle,
            }
        )

    mean_single = statistics.fmean(best_single_objectives) if best_single_objectives else math.nan
    mean_workload = statistics.fmean(workload_objectives) if workload_objectives else math.nan
    mean_learned = statistics.fmean(learned_objectives) if learned_objectives else math.nan
    mean_oracle = statistics.fmean(oracle_objectives) if oracle_objectives else math.nan
    return {
        "pilot_workload_matrix": matrix,
        "best_single_model": single_model,
        "best_single_pilot_objective": single_score,
        "workload_policy": workload_router,
        "best_single_holdout_objective": mean_single,
        "workload_holdout_objective": mean_workload,
        "learned_router_holdout_objective": mean_learned,
        "oracle_holdout_objective": mean_oracle,
        "workload_opportunity": mean_single - mean_workload if best_single_objectives and workload_objectives else math.nan,
        "incremental_probe_value": mean_workload - mean_oracle if workload_objectives and oracle_objectives else math.nan,
        "router_regret": mean_learned - mean_oracle if learned_objectives and oracle_objectives else math.nan,
        "gain_over_best_single": mean_single - mean_learned if best_single_objectives and learned_objectives else math.nan,
        "instance_count": len(per_instance),
        "instances": per_instance,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Run roots containing AutoResearch run_summary.json files")
    parser.add_argument("--output", required=True)
    parser.add_argument("--improvement-threshold", type=float, default=None)
    parser.add_argument("--cost-metric", default="wall_seconds", choices=["wall_seconds", "usd", "tokens"])
    parser.add_argument("--pilot-split", default="pilot")
    parser.add_argument("--holdout-split", default="holdout")
    parser.add_argument(
        "--router-feature-set",
        default="workload_plus_probe",
        choices=[
            "probe_only",
            "workload_only",
            "workload_plus_probe",
            "shortprobe_only",
            "workload_plus_shortprobe",
            "workload_plus_interactions",
            "leaky_current",
        ],
    )
    parser.add_argument("--knn-k", type=int, default=3)
    parser.add_argument("--probe-roots", nargs="*", default=None, help="Optional short-probe run roots to merge into router-visible features")
    args = parser.parse_args(argv)

    roots = [Path(root) for root in args.roots]
    probe_roots = [Path(root) for root in (args.probe_roots or [])]
    probe_feature_index = load_probe_feature_index(probe_roots) if probe_roots else {}
    records = load_attempt_records(
        roots,
        improvement_threshold=args.improvement_threshold,
        router_feature_set=args.router_feature_set,
        probe_feature_index=probe_feature_index,
    )
    bundles = build_instance_bundles(records)
    report = evaluate_accounting(
        bundles,
        pilot_split=args.pilot_split,
        holdout_split=args.holdout_split,
        cost_metric=args.cost_metric,
        knn_k=args.knn_k,
    )
    report["attempt_records"] = len(records)
    report["probe_instance_count"] = len(probe_feature_index)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "instance_count": report["instance_count"]}, indent=2))


if __name__ == "__main__":
    main()
