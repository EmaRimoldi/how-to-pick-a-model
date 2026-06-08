"""Evaluate router-visible signal ablations for AutoResearch task-mode prediction.

The goal is to test how much task-mode information remains after removing leaky
features from Z. Inputs are run directories containing baseline verifier output
and manifests; the classifier is a simple leave-one-out nearest-centroid model.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BaselineRecord:
    run_dir: Path
    task_mode_true: str
    seed: int | None
    features: dict[str, float]


def _capture_float(text: str, name: str) -> float:
    match = re.search(rf"^{name}\s*=\s*([^\n#]+)", text, re.MULTILINE)
    if not match:
        return 0.0
    raw = match.group(1).strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _capture_bool(text: str, name: str) -> float:
    match = re.search(rf"^{name}\s*=\s*(True|False)", text, re.MULTILINE)
    if not match:
        return 0.0
    return 1.0 if match.group(1) == "True" else 0.0


def _template_features(template_path: Path | None) -> dict[str, float]:
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
    optimizer_match = re.search(r'^OPTIMIZER\s*=\s*"([^"]+)"', text, re.MULTILINE)
    optimizer = optimizer_match.group(1) if optimizer_match else ""
    return {
        "depth": _capture_float(text, "DEPTH"),
        "base_channels": _capture_float(text, "BASE_CHANNELS"),
        "dropout_rate": _capture_float(text, "DROPOUT_RATE"),
        "learning_rate": _capture_float(text, "LEARNING_RATE"),
        "weight_decay": _capture_float(text, "WEIGHT_DECAY"),
        "batch_size": _capture_float(text, "BATCH_SIZE"),
        "use_lr_schedule": _capture_bool(text, "USE_LR_SCHEDULE"),
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


def load_records(roots: list[Path]) -> list[BaselineRecord]:
    records: list[BaselineRecord] = []
    for root in roots:
        for run_dir in sorted(path.parent for path in root.glob("**/run_manifest.json")):
            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            task_mode_true = manifest.get("task_mode_true")
            if not task_mode_true:
                continue
            config = manifest.get("config") or {}
            benchmark = config.get("benchmark") or {}
            overrides = benchmark.get("instance_overrides") or {}
            template_path = benchmark.get("template_path")
            features: dict[str, float] = {
                "train_subset_size": float(overrides.get("train_subset_size", 0.0)),
                "val_subset_size": float(overrides.get("val_subset_size", 0.0)),
                "label_noise_rate": float(overrides.get("label_noise_rate", 0.0)),
                "imbalance_ratio": float(overrides.get("imbalance_ratio", 1.0)),
                "max_train_steps": float(overrides.get("max_train_steps", 0.0)),
            }
            features.update(_template_features(Path(template_path) if template_path else None))
            features.update(_baseline_probe_features(run_dir))
            records.append(
                BaselineRecord(
                    run_dir=run_dir,
                    task_mode_true=str(task_mode_true),
                    seed=manifest.get("instance_seed"),
                    features=features,
                )
            )
    return records


FEATURE_SETS: dict[str, list[str]] = {
    "leaky_current": [
        "train_subset_size",
        "val_subset_size",
        "label_noise_rate",
        "imbalance_ratio",
        "max_train_steps",
        "depth",
        "base_channels",
        "dropout_rate",
        "learning_rate",
        "weight_decay",
        "batch_size",
        "use_lr_schedule",
        "optimizer_is_adam",
        "optimizer_is_sgd",
        "baseline_val_loss",
        "baseline_val_accuracy",
        "baseline_training_seconds",
        "baseline_total_seconds",
        "baseline_param_count",
        "baseline_total_steps",
    ],
    "probe_only": [
        "baseline_val_loss",
        "baseline_val_accuracy",
        "baseline_training_seconds",
        "baseline_total_seconds",
        "baseline_param_count",
        "baseline_total_steps",
    ],
    "probe_plus_budget": [
        "max_train_steps",
        "baseline_val_loss",
        "baseline_val_accuracy",
        "baseline_training_seconds",
        "baseline_total_seconds",
        "baseline_param_count",
        "baseline_total_steps",
    ],
    "budget_only": ["max_train_steps"],
}


def _vector(record: BaselineRecord, feature_names: list[str]) -> list[float]:
    return [float(record.features.get(name, 0.0)) for name in feature_names]


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def evaluate_feature_set(records: list[BaselineRecord], feature_names: list[str]) -> dict[str, Any]:
    if not records:
        return {"count": 0, "accuracy": 0.0, "macro_accuracy": 0.0, "confusion": {}}
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    correct = 0
    per_mode_correct: Counter[str] = Counter()
    per_mode_total: Counter[str] = Counter()
    for idx, record in enumerate(records):
        train = [r for j, r in enumerate(records) if j != idx]
        centroids: dict[str, list[float]] = {}
        grouped: dict[str, list[list[float]]] = defaultdict(list)
        for other in train:
            grouped[other.task_mode_true].append(_vector(other, feature_names))
        for mode, vectors in grouped.items():
            dims = len(vectors[0])
            centroids[mode] = [sum(v[d] for v in vectors) / len(vectors) for d in range(dims)]
        target = _vector(record, feature_names)
        pred = min(centroids, key=lambda mode: _distance(target, centroids[mode]))
        confusion[record.task_mode_true][pred] += 1
        per_mode_total[record.task_mode_true] += 1
        if pred == record.task_mode_true:
            correct += 1
            per_mode_correct[record.task_mode_true] += 1
    macro = sum(per_mode_correct[m] / per_mode_total[m] for m in per_mode_total) / len(per_mode_total)
    return {
        "count": len(records),
        "accuracy": correct / len(records),
        "macro_accuracy": macro,
        "confusion": {mode: dict(counter) for mode, counter in sorted(confusion.items())},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Run roots containing baseline verifier output")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    records = load_records([Path(item) for item in args.roots])
    payload = {
        "record_count": len(records),
        "feature_sets": {
            name: evaluate_feature_set(records, features) for name, features in FEATURE_SETS.items()
        },
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
