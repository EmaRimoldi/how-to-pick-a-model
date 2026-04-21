"""Train a routing-only student.

The preferred future path is LoRA on an instruct model. The current local
environment may not have PEFT installed, so this entrypoint implements a
lightweight supervised routing student that is deterministic, cheap, and emits
the same six-mode probability contract as an LLM router.
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import random
from pathlib import Path
from typing import Any

import yaml
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from vao.estimators import jsd, routing_regret
from vao.logging_utils import now_iso
from vao.taxonomy import MODES, normalize_mode_probs
from vao.training.routing_features import DEFAULT_MAX_SOURCE_CHARS, record_to_text


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def split_records(records: list[dict[str, Any]], *, dev_fraction: float, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not records:
        return [], []
    indices = list(range(len(records)))
    random.Random(seed).shuffle(indices)
    dev_count = max(1, int(round(len(records) * dev_fraction))) if len(records) > 1 else 0
    dev_indices = set(indices[:dev_count])
    train = [record for index, record in enumerate(records) if index not in dev_indices]
    dev = [record for index, record in enumerate(records) if index in dev_indices]
    if not train and dev:
        train.append(dev.pop())
    return train, dev


def train(records: list[dict[str, Any]], config: dict[str, Any]) -> Pipeline:
    max_source_chars = int(config.get("max_source_chars", DEFAULT_MAX_SOURCE_CHARS))
    texts = [record_to_text(record, max_source_chars=max_source_chars) for record in records]
    labels = [str(record["productive_mode_top1"]) for record in records]
    if len(set(labels)) < 2:
        classifier = DummyClassifier(strategy="most_frequent")
    else:
        classifier = LogisticRegression(
            max_iter=int(config.get("max_iter", 1000)),
            class_weight=str(config.get("class_weight", "balanced")),
            random_state=int(config.get("seed", 5105)),
        )
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=int(config.get("max_features", 5000)),
                    ngram_range=tuple(config.get("ngram_range", [1, 2])),
                    min_df=int(config.get("min_df", 1)),
                ),
            ),
            ("classifier", classifier),
        ]
    )
    pipeline.fit(texts, labels)
    return pipeline


def predict_mode_probs(model: Pipeline, text: str) -> dict[str, float]:
    if not hasattr(model, "predict_proba"):
        top = str(model.predict([text])[0])
        return {mode: 1.0 if mode == top else 0.0 for mode in MODES}
    probs = model.predict_proba([text])[0]
    classes = [str(item) for item in model.classes_]
    mapped = {mode: 0.0 for mode in MODES}
    for label, probability in zip(classes, probs, strict=True):
        if label in mapped:
            mapped[label] = float(probability)
    return normalize_mode_probs(mapped)


def evaluate_records(model: Pipeline, records: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    max_source_chars = int(config.get("max_source_chars", DEFAULT_MAX_SOURCE_CHARS))
    rows = []
    for record in records:
        text = record_to_text(record, max_source_chars=max_source_chars)
        predicted_probs = predict_mode_probs(model, text)
        predicted_top1 = max(MODES, key=lambda mode: predicted_probs[mode])
        target_top1 = str(record["productive_mode_top1"])
        pstar = normalize_mode_probs(record["productive_mode_distribution"])
        gains = {mode: float(record["verified_gain_per_mode"][mode]) for mode in MODES}
        best_gain = max(gains.values())
        expected_gain = sum(predicted_probs[mode] * gains[mode] for mode in MODES)
        original_probs = normalize_mode_probs(record["original_mode_probs"])
        original_top1 = max(MODES, key=lambda mode: original_probs[mode])
        rows.append(
            {
                "run_id": record.get("run_id"),
                "profile_id": record.get("profile_id"),
                "step": record.get("step"),
                "target_top1": target_top1,
                "predicted_top1": predicted_top1,
                "predicted_mode_probs": predicted_probs,
                "top1_correct": predicted_top1 == target_top1,
                "original_top1": original_top1,
                "original_top1_correct": original_top1 == target_top1,
                "predicted_top1_regret": routing_regret(gains, predicted_top1),
                "predicted_expected_regret": float(best_gain - expected_gain),
                "original_top1_regret": float(record["original_top1_regret"]),
                "predicted_jsd": jsd(predicted_probs, pstar),
                "original_jsd": jsd(original_probs, pstar),
            }
        )
    return summarize_predictions(rows)


def summarize_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None and math.isfinite(float(row[key]))]
        return sum(values) / len(values) if values else None

    return {
        "record_count": len(rows),
        "top1_accuracy": mean("top1_correct"),
        "original_top1_accuracy": mean("original_top1_correct"),
        "mean_predicted_top1_regret": mean("predicted_top1_regret"),
        "mean_predicted_expected_regret": mean("predicted_expected_regret"),
        "mean_original_top1_regret": mean("original_top1_regret"),
        "mean_predicted_jsd": mean("predicted_jsd"),
        "mean_original_jsd": mean("original_jsd"),
        "predictions": rows,
    }


def save_model(path: Path, model: Pipeline, config: dict[str, Any], train_summary: dict[str, Any], eval_summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "modes": MODES,
        "config": config,
        "train_summary": train_summary,
        "eval_summary": eval_summary,
        "created_at": now_iso(),
    }
    with path.open("wb") as handle:
        pickle.dump(payload, handle)


def run_training(config: dict[str, Any]) -> dict[str, Any]:
    training = config.get("training", config)
    records_path = Path(training["train_records"])
    records = load_jsonl(records_path)
    train_records, eval_records = split_records(
        records,
        dev_fraction=float(training.get("dev_fraction", 0.25)),
        seed=int(training.get("seed", 5105)),
    )
    model = train(train_records, training)
    train_metrics = evaluate_records(model, train_records, training)
    eval_metrics = evaluate_records(model, eval_records, training) if eval_records else {"record_count": 0}
    output_dir = Path(training.get("output_dir", "training/phase5_routing_student"))
    model_path = output_dir / "model.pkl"
    train_summary = {
        "status": "completed",
        "base_model": training.get("base_model", "sklearn-tfidf-logreg"),
        "implementation": "tfidf_logistic_regression_router",
        "lora_used": False,
        "lora_unavailable_reason": training.get("lora_unavailable_reason", "peft_not_installed_or_not_required_for_routing_only"),
        "record_count": len(records),
        "train_count": len(train_records),
        "eval_count": len(eval_records),
        "model_path": str(model_path),
        "train_metrics": {key: value for key, value in train_metrics.items() if key != "predictions"},
        "created_at": now_iso(),
    }
    save_model(model_path, model, training, train_summary, eval_metrics)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "train_predictions.json").write_text(json.dumps(train_metrics, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    (output_dir / "eval_predictions.json").write_text(json.dumps(eval_metrics, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    train_out = Path(training.get("train_summary_out", "artifacts/phase5_routing_train_summary.json"))
    eval_out = Path(training.get("eval_summary_out", "artifacts/phase5_routing_eval_summary.json"))
    train_out.parent.mkdir(parents=True, exist_ok=True)
    train_out.write_text(json.dumps(train_summary, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    eval_out.write_text(json.dumps(eval_metrics, indent=2, sort_keys=True, allow_nan=True), encoding="utf-8")
    return {"train_summary": train_summary, "eval_summary": eval_metrics}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    result = run_training(config)
    printable = {
        "status": result["train_summary"]["status"],
        "train_count": result["train_summary"]["train_count"],
        "eval_count": result["train_summary"]["eval_count"],
        "model_path": result["train_summary"]["model_path"],
        "eval": {key: value for key, value in result["eval_summary"].items() if key != "predictions"},
    }
    print(json.dumps(printable, indent=2, sort_keys=True, allow_nan=True))


if __name__ == "__main__":
    main()
