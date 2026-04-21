"""Offline routing-student comparisons using existing teacher data only."""

from __future__ import annotations

import argparse
import json
import math
import pickle
import statistics
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from vao.analysis.replay_routing import compact_comparison, default_policies, evaluate_policies
from vao.estimators import jsd, routing_regret
from vao.logging_utils import now_iso, read_jsonl, write_json
from vao.taxonomy import MODES, normalize_mode_probs
from vao.training.routing_features import DEFAULT_MAX_SOURCE_CHARS, record_to_text, structured_features_from_record


@dataclass(frozen=True)
class ModelSpec:
    name: str
    feature_type: str
    config: dict[str, Any]


MODEL_SPECS = [
    ModelSpec("tfidf_word_logreg_balanced", "text", {"analyzer": "word", "ngram_range": (1, 2), "class_weight": "balanced"}),
    ModelSpec("tfidf_char_logreg_balanced", "text", {"analyzer": "char_wb", "ngram_range": (3, 5), "class_weight": "balanced"}),
    ModelSpec("tfidf_word_multinomial_nb", "text", {"analyzer": "word", "ngram_range": (1, 2), "classifier": "nb"}),
    ModelSpec("structured_logreg_balanced", "structured", {"class_weight": "balanced"}),
]


def run_offline_experiments(config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("offline_routing", config)
    dataset_path = Path(settings["dataset"])
    records = read_jsonl(dataset_path)
    output_dir = Path(settings.get("output_dir", "training/offline_routing_student"))
    output_dir.mkdir(parents=True, exist_ok=True)
    max_source_chars = int(settings.get("max_source_chars", DEFAULT_MAX_SOURCE_CHARS))
    cv_results = []
    for spec in MODEL_SPECS:
        cv_results.append(evaluate_model_leave_one_out(records, spec, max_source_chars=max_source_chars))
    best = min(
        cv_results,
        key=lambda item: (
            _sort_metric(item.get("mean_expected_regret")),
            _sort_metric(item.get("mean_top1_regret")),
            -float(item.get("top1_accuracy") or 0.0),
        ),
    )
    best_spec = next(spec for spec in MODEL_SPECS if spec.name == best["model"])
    model, train_info = fit_model(records, best_spec, max_source_chars=max_source_chars)
    model_path = output_dir / "model.pkl"
    payload = {
        "model": model,
        "modes": MODES,
        "feature_type": best_spec.feature_type,
        "model_name": best_spec.name,
        "config": {**settings, "max_source_chars": max_source_chars},
        "train_summary": {
            "status": "completed",
            "created_at": now_iso(),
            "dataset": str(dataset_path),
            "record_count": len(records),
            "selected_model": best_spec.name,
            "selection_metric": "lowest_leave_one_out_mean_expected_regret",
            "model_path": str(model_path),
            "train_info": train_info,
        },
        "eval_summary": best,
    }
    with model_path.open("wb") as handle:
        pickle.dump(payload, handle)

    replay = compact_comparison(
        evaluate_policies(records, default_policies(records, student_model_path=Path(settings.get("previous_student_model", ""))))
    )
    profile_holdout = evaluate_profile_holdout(records, best_spec, max_source_chars=max_source_chars)
    supplemental_models = load_supplemental_eval_summaries(settings.get("supplemental_eval_summaries", []))
    comparison = {
        "dataset": str(dataset_path),
        "record_count": len(records),
        "model_selection": payload["train_summary"],
        "leave_one_out_models": cv_results,
        "profile_holdout_for_selected_model": profile_holdout,
        "replay_baselines": replay["policies"],
        "supplemental_models": supplemental_models,
    }
    leaderboard = build_leaderboard(comparison)
    train_summary = payload["train_summary"]
    eval_summary = {
        "selected_model": best_spec.name,
        "leave_one_out": best,
        "profile_holdout": profile_holdout,
    }
    write_json(Path(settings.get("train_summary_out", "artifacts/offline_routing_train_summary.json")), train_summary)
    write_json(Path(settings.get("eval_summary_out", "artifacts/offline_routing_eval_summary.json")), eval_summary)
    write_json(Path(settings.get("model_comparison_out", "artifacts/offline_routing_model_comparison.json")), comparison)
    write_json(Path(settings.get("leaderboard_out", "artifacts/offline_router_leaderboard.json")), leaderboard)
    write_leaderboard_markdown(leaderboard, Path(settings.get("leaderboard_md_out", "artifacts/offline_router_leaderboard.md")))
    return {"train_summary": train_summary, "eval_summary": eval_summary, "comparison": comparison, "leaderboard": leaderboard}


def evaluate_model_leave_one_out(records: list[dict[str, Any]], spec: ModelSpec, *, max_source_chars: int) -> dict[str, Any]:
    rows = []
    for index in range(len(records)):
        train_records = [record for j, record in enumerate(records) if j != index]
        test_record = records[index]
        model, _ = fit_model(train_records, spec, max_source_chars=max_source_chars)
        probs = predict_record(model, test_record, spec.feature_type, max_source_chars=max_source_chars)
        rows.append(_prediction_row(test_record, probs))
    return summarize_prediction_rows(spec.name, rows)


def evaluate_profile_holdout(records: list[dict[str, Any]], spec: ModelSpec, *, max_source_chars: int) -> dict[str, Any]:
    by_profile: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_profile.setdefault(str(record.get("profile_id")), []).append(record)
    results = {}
    all_rows = []
    for profile, test_records in sorted(by_profile.items()):
        train_records = [record for record in records if str(record.get("profile_id")) != profile]
        if not train_records:
            continue
        model, _ = fit_model(train_records, spec, max_source_chars=max_source_chars)
        rows = [_prediction_row(record, predict_record(model, record, spec.feature_type, max_source_chars=max_source_chars)) for record in test_records]
        results[profile] = summarize_prediction_rows(f"profile_holdout_{profile}", rows)
        all_rows.extend(rows)
    return {
        "overall": summarize_prediction_rows("profile_holdout_overall", all_rows),
        "by_profile": results,
    }


def fit_model(records: list[dict[str, Any]], spec: ModelSpec, *, max_source_chars: int) -> tuple[Any, dict[str, Any]]:
    labels = [str(record["productive_mode_top1"]) for record in records]
    if spec.feature_type == "structured":
        x_train = [structured_features_from_record(record) for record in records]
        if len(set(labels)) < 2:
            model = Pipeline([("dict", DictVectorizer()), ("classifier", DummyClassifier(strategy="most_frequent"))])
        else:
            model = Pipeline(
                [
                    ("dict", DictVectorizer()),
                    (
                        "classifier",
                        LogisticRegression(
                            max_iter=5000,
                            class_weight=spec.config.get("class_weight"),
                            random_state=5105,
                        ),
                    ),
                ]
            )
    else:
        x_train = [record_to_text(record, max_source_chars=max_source_chars) for record in records]
        if len(set(labels)) < 2:
            classifier = DummyClassifier(strategy="most_frequent")
        elif spec.config.get("classifier") == "nb":
            classifier = MultinomialNB(alpha=0.5)
        else:
            classifier = LogisticRegression(
                max_iter=5000,
                class_weight=spec.config.get("class_weight"),
                random_state=5105,
            )
        model = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        analyzer=spec.config.get("analyzer", "word"),
                        ngram_range=spec.config.get("ngram_range", (1, 2)),
                        max_features=int(spec.config.get("max_features", 5000)),
                        min_df=1,
                    ),
                ),
                ("classifier", classifier),
            ]
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(x_train, labels)
    return model, {"trained_records": len(records), "classes": sorted(set(labels)), "feature_type": spec.feature_type}


def predict_record(model: Any, record: dict[str, Any], feature_type: str, *, max_source_chars: int) -> dict[str, float]:
    x_item = (
        structured_features_from_record(record)
        if feature_type == "structured"
        else record_to_text(record, max_source_chars=max_source_chars)
    )
    if hasattr(model, "predict_proba"):
        raw = model.predict_proba([x_item])[0]
        classes = [str(item) for item in model.classes_]
        probs = {mode: 0.0 for mode in MODES}
        for label, probability in zip(classes, raw, strict=True):
            if label in probs:
                probs[label] = float(probability)
        return normalize_mode_probs(probs)
    predicted = str(model.predict([x_item])[0])
    return {mode: 1.0 if mode == predicted else 0.0 for mode in MODES}


def _prediction_row(record: dict[str, Any], probs: dict[str, float]) -> dict[str, Any]:
    predicted_top1 = max(MODES, key=lambda mode: probs[mode])
    target_top1 = str(record["productive_mode_top1"])
    gains = {mode: float(record["verified_gain_per_mode"][mode]) for mode in MODES}
    best_gain = max(gains.values())
    expected_gain = sum(probs[mode] * gains[mode] for mode in MODES)
    pstar = normalize_mode_probs(record["productive_mode_distribution"])
    return {
        "run_id": record.get("run_id"),
        "profile_id": record.get("profile_id"),
        "step": record.get("step"),
        "target_top1": target_top1,
        "predicted_top1": predicted_top1,
        "predicted_mode_probs": probs,
        "top1_correct": predicted_top1 == target_top1,
        "top1_regret": routing_regret(gains, predicted_top1),
        "expected_regret": float(best_gain - expected_gain),
        "jsd": jsd(probs, pstar),
        "kl": _kl(probs, pstar),
        "brier_to_productive_distribution": sum((probs[mode] - pstar[mode]) ** 2 for mode in MODES) / len(MODES),
        "confidence": max(probs.values()),
    }


def summarize_prediction_rows(model_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    y_true = [row["target_top1"] for row in rows]
    y_pred = [row["predicted_top1"] for row in rows]
    return {
        "model": model_name,
        "record_count": len(rows),
        "top1_accuracy": _mean([row["top1_correct"] for row in rows]),
        "macro_f1": float(f1_score(y_true, y_pred, labels=MODES, average="macro", zero_division=0)) if rows else None,
        "weighted_f1": float(f1_score(y_true, y_pred, labels=MODES, average="weighted", zero_division=0)) if rows else None,
        "mean_top1_regret": _mean([row["top1_regret"] for row in rows]),
        "mean_expected_regret": _mean([row["expected_regret"] for row in rows]),
        "mean_jsd": _mean([row["jsd"] for row in rows]),
        "mean_kl": _mean([row["kl"] for row in rows]),
        "mean_brier": _mean([row["brier_to_productive_distribution"] for row in rows]),
        "ece_5bin": expected_calibration_error(rows, bins=5),
        "predicted_mode_counts": dict(sorted({mode: sum(1 for row in rows if row["predicted_top1"] == mode) for mode in MODES}.items())),
        "target_mode_counts": dict(sorted({mode: sum(1 for row in rows if row["target_top1"] == mode) for mode in MODES}.items())),
        "rows": rows,
    }


def expected_calibration_error(rows: list[dict[str, Any]], bins: int = 5) -> float | None:
    if not rows:
        return None
    total = 0.0
    for bucket in range(bins):
        lo = bucket / bins
        hi = (bucket + 1) / bins
        selected = [row for row in rows if lo < float(row["confidence"]) <= hi or (bucket == 0 and float(row["confidence"]) == 0.0)]
        if not selected:
            continue
        accuracy = statistics.fmean(float(row["top1_correct"]) for row in selected)
        confidence = statistics.fmean(float(row["confidence"]) for row in selected)
        total += (len(selected) / len(rows)) * abs(accuracy - confidence)
    return total


def build_leaderboard(comparison: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for result in comparison["leave_one_out_models"]:
        entries.append(_leaderboard_entry(result, source="leave_one_out_model"))
    for result in comparison.get("supplemental_models", []):
        entries.append(_leaderboard_entry(result, source=result.get("source", "supplemental_model")))
    for name, result in comparison["replay_baselines"].items():
        entries.append(
            {
                "model": name,
                "source": "replay_baseline",
                "record_count": result["record_count"],
                "top1_accuracy": result["top1_accuracy"],
                "macro_f1": result["macro_f1"],
                "weighted_f1": result["weighted_f1"],
                "mean_top1_regret": result["mean_top1_regret"],
                "mean_expected_regret": result["mean_expected_regret"],
                "mean_jsd": result["mean_jsd_to_productive"],
                "mean_kl": result["mean_kl_to_productive"],
                "ece_5bin": None,
            }
        )
    entries = sorted(entries, key=lambda item: (_sort_metric(item["mean_expected_regret"]), _sort_metric(item["mean_top1_regret"])))
    return {
        "selection_note": "Lower expected regret is primary; lower top-1 regret breaks ties.",
        "entries": entries,
    }


def load_supplemental_eval_summaries(paths: list[str] | None) -> list[dict[str, Any]]:
    summaries = []
    for raw_path in paths or []:
        path = Path(raw_path)
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        metrics = dict(payload.get("eval_metrics", payload))
        if not metrics:
            continue
        metrics.setdefault("model", payload.get("model", "supplemental_model"))
        metrics.setdefault("record_count", payload.get("eval_count", metrics.get("record_count")))
        metrics["source"] = payload.get("leaderboard_source", "supplemental_split_model")
        summaries.append(metrics)
    return summaries


def _leaderboard_entry(result: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "model": result["model"],
        "source": source,
        "record_count": result["record_count"],
        "top1_accuracy": result["top1_accuracy"],
        "macro_f1": result["macro_f1"],
        "weighted_f1": result["weighted_f1"],
        "mean_top1_regret": result["mean_top1_regret"],
        "mean_expected_regret": result["mean_expected_regret"],
        "mean_jsd": result["mean_jsd"],
        "mean_kl": result["mean_kl"],
        "ece_5bin": result["ece_5bin"],
    }


def write_leaderboard_markdown(leaderboard: dict[str, Any], path: Path) -> None:
    lines = [
        "# Offline Router Leaderboard",
        "",
        leaderboard["selection_note"],
        "",
        "| rank | model | source | accuracy | macro F1 | weighted F1 | expected regret | top-1 regret | JSD | ECE |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, entry in enumerate(leaderboard["entries"], start=1):
        lines.append(
            f"| {index} | `{entry['model']}` | `{entry['source']}` | `{entry['top1_accuracy']}` | "
            f"`{entry['macro_f1']}` | `{entry['weighted_f1']}` | `{entry['mean_expected_regret']}` | "
            f"`{entry['mean_top1_regret']}` | `{entry['mean_jsd']}` | `{entry['ece_5bin']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mean(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(numeric) if numeric else None


def _kl(predicted: dict[str, float], target: dict[str, float], epsilon: float = 1e-12) -> float:
    predicted = normalize_mode_probs(predicted)
    target = normalize_mode_probs(target)
    total = 0.0
    for mode in MODES:
        q = max(float(target[mode]), epsilon)
        p = max(float(predicted[mode]), epsilon)
        total += q * math.log(q / p, 2)
    return float(total)


def _sort_metric(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.inf
    return numeric if math.isfinite(numeric) else math.inf


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    result = run_offline_experiments(config)
    print(
        json.dumps(
            {
                "selected_model": result["train_summary"]["selected_model"],
                "record_count": result["train_summary"]["record_count"],
                "leaderboard_entries": len(result["leaderboard"]["entries"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
