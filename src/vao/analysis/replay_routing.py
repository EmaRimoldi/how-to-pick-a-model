"""Replay routing policies on logged counterfactual branch evaluations."""

from __future__ import annotations

import argparse
import json
import math
import pickle
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Protocol

from sklearn.metrics import f1_score

from vao.estimators import jsd, routing_regret
from vao.logging_utils import read_jsonl, write_json
from vao.schemas import StepRecord
from vao.taxonomy import MODES, normalize_mode_probs
from vao.training.routing_features import DEFAULT_MAX_SOURCE_CHARS, record_to_text
from vao.training.train_routing_lora import predict_mode_probs


class RouterPolicy(Protocol):
    name: str

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        ...


class OriginalTeacherRouter:
    name = "original_teacher"

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        return normalize_mode_probs(record.get("original_mode_probs", {}))


class AlwaysModeRouter:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.name = f"always_{mode}"

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        return {mode: 1.0 if mode == self.mode else 0.0 for mode in MODES}


class FrequencyRouter:
    name = "frequency_baseline"

    def __init__(self, records: list[dict[str, Any]]) -> None:
        counts = Counter(str(record.get("productive_mode_top1")) for record in records)
        total = sum(counts.get(mode, 0) for mode in MODES)
        if total == 0:
            self.probs = {mode: 1.0 / len(MODES) for mode in MODES}
        else:
            self.probs = {mode: counts.get(mode, 0) / total for mode in MODES}
            self.probs = normalize_mode_probs(self.probs)

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        return dict(self.probs)


class RandomRouter:
    name = "random_seeded"

    def __init__(self, seed: int = 20260421) -> None:
        self.seed = seed

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        rng = random.Random(self.seed + index)
        selected = rng.choice(MODES)
        return {mode: 1.0 if mode == selected else 0.0 for mode in MODES}


class SavedStudentRouter:
    name = "saved_routing_student"

    def __init__(self, model_path: Path, *, max_source_chars: int = DEFAULT_MAX_SOURCE_CHARS) -> None:
        self.model_path = model_path
        self.max_source_chars = max_source_chars
        with model_path.open("rb") as handle:
            self.payload = pickle.load(handle)

    def mode_probs(self, record: dict[str, Any], index: int) -> dict[str, float]:
        text = record_to_text(record, max_source_chars=self.max_source_chars)
        return predict_mode_probs(self.payload["model"], text)


def default_policies(records: list[dict[str, Any]], *, student_model_path: Path | None = None, seed: int = 20260421) -> list[RouterPolicy]:
    policies: list[RouterPolicy] = [OriginalTeacherRouter()]
    if student_model_path and student_model_path.exists():
        policies.append(SavedStudentRouter(student_model_path))
    policies.extend(AlwaysModeRouter(mode) for mode in MODES)
    policies.append(FrequencyRouter(records))
    policies.append(RandomRouter(seed=seed))
    return policies


def evaluate_policy(records: list[dict[str, Any]], policy: RouterPolicy) -> dict[str, Any]:
    rows = []
    visible_losses_by_run: dict[str, list[float]] = defaultdict(list)
    for index, record in enumerate(records):
        probs = normalize_mode_probs(policy.mode_probs(record, index))
        predicted_top1 = max(MODES, key=lambda mode: probs[mode])
        target_top1 = str(record["productive_mode_top1"])
        gains = {mode: float(record["verified_gain_per_mode"][mode]) for mode in MODES}
        best_gain = max(gains.values())
        expected_gain = sum(probs[mode] * gains[mode] for mode in MODES)
        pstar = normalize_mode_probs(record["productive_mode_distribution"])
        step = _load_step(record)
        chosen_loss = _chosen_loss(step, predicted_top1)
        if chosen_loss is not None and math.isfinite(chosen_loss):
            visible_losses_by_run[str(record.get("run_id"))].append(chosen_loss)
        rows.append(
            {
                "run_id": record.get("run_id"),
                "profile_id": record.get("profile_id"),
                "step": record.get("step"),
                "target_top1": target_top1,
                "predicted_top1": predicted_top1,
                "mode_probs": probs,
                "top1_correct": predicted_top1 == target_top1,
                "top1_regret": routing_regret(gains, predicted_top1),
                "expected_regret": float(best_gain - expected_gain),
                "jsd_to_productive": jsd(probs, pstar),
                "kl_to_productive": _kl(probs, pstar),
                "chosen_logged_branch_loss": chosen_loss,
            }
        )
    return summarize_replay_rows(policy.name, rows, visible_losses_by_run)


def evaluate_policies(records: list[dict[str, Any]], policies: list[RouterPolicy]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "replay_type": "one_step_logged_counterfactual_replay",
        "caveat": (
            "Each decision is evaluated against branches logged at that checkpoint. "
            "If a router would choose a different branch, later logged checkpoints are not guaranteed to be reachable."
        ),
        "policies": {policy.name: evaluate_policy(records, policy) for policy in policies},
    }


def summarize_replay_rows(name: str, rows: list[dict[str, Any]], visible_losses_by_run: dict[str, list[float]]) -> dict[str, Any]:
    y_true = [row["target_top1"] for row in rows]
    y_pred = [row["predicted_top1"] for row in rows]
    visible_best_by_run = {
        run_id: min(losses) for run_id, losses in visible_losses_by_run.items() if losses
    }
    return {
        "policy": name,
        "record_count": len(rows),
        "top1_accuracy": _mean([row["top1_correct"] for row in rows]),
        "macro_f1": float(f1_score(y_true, y_pred, labels=MODES, average="macro", zero_division=0)) if rows else None,
        "weighted_f1": float(f1_score(y_true, y_pred, labels=MODES, average="weighted", zero_division=0)) if rows else None,
        "mean_top1_regret": _mean([row["top1_regret"] for row in rows]),
        "mean_expected_regret": _mean([row["expected_regret"] for row in rows]),
        "median_top1_regret": _median([row["top1_regret"] for row in rows]),
        "mean_jsd_to_productive": _mean([row["jsd_to_productive"] for row in rows]),
        "mean_kl_to_productive": _mean([row["kl_to_productive"] for row in rows]),
        "predicted_mode_counts": dict(Counter(y_pred)),
        "target_mode_counts": dict(Counter(y_true)),
        "visible_best_loss_by_run_logged_replay": visible_best_by_run,
        "mean_visible_best_loss_logged_replay": _mean(list(visible_best_by_run.values())),
        "rows": rows,
    }


def write_markdown(comparison: dict[str, Any], path: Path) -> None:
    rows = [
        "# Replay Router Comparison",
        "",
        f"Replay type: `{comparison['replay_type']}`",
        "",
        comparison["caveat"],
        "",
        "| policy | accuracy | macro F1 | weighted F1 | top-1 regret | expected regret | JSD | logged best loss |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in sorted(comparison["policies"].items()):
        rows.append(
            f"| `{name}` | `{result['top1_accuracy']}` | `{result['macro_f1']}` | `{result['weighted_f1']}` | "
            f"`{result['mean_top1_regret']}` | `{result['mean_expected_regret']}` | "
            f"`{result['mean_jsd_to_productive']}` | `{result['mean_visible_best_loss_logged_replay']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_step(record: dict[str, Any]) -> StepRecord | None:
    path_value = record.get("source_step_record_path")
    if not path_value:
        return None
    path = Path(str(path_value))
    if not path.exists():
        return None
    try:
        return StepRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - replay metrics should remain available without loss fields.
        return None


def _chosen_loss(step: StepRecord | None, mode: str) -> float | None:
    if step is None:
        return None
    for branch in step.branches:
        if branch.declared_mode == mode:
            return float(branch.latent_loss)
    return None


def _mean(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(numeric) if numeric else None


def _median(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.median(numeric) if numeric else None


def _kl(predicted: dict[str, float], target: dict[str, float], epsilon: float = 1e-12) -> float:
    predicted = normalize_mode_probs(predicted)
    target = normalize_mode_probs(target)
    total = 0.0
    for mode in MODES:
        q = max(float(target[mode]), epsilon)
        p = max(float(predicted[mode]), epsilon)
        total += q * math.log(q / p, 2)
    return float(total)


def compact_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    compact = {key: value for key, value in comparison.items() if key != "policies"}
    compact["policies"] = {
        name: {key: value for key, value in result.items() if key != "rows"}
        for name, result in comparison["policies"].items()
    }
    return compact


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--student_model", default="training/phase5_routing_student/model.pkl")
    parser.add_argument("--json_out", required=True)
    parser.add_argument("--md_out", required=True)
    parser.add_argument("--seed", type=int, default=20260421)
    args = parser.parse_args(argv)
    records = read_jsonl(Path(args.dataset))
    student_path = Path(args.student_model) if args.student_model else None
    policies = default_policies(records, student_model_path=student_path, seed=args.seed)
    comparison = evaluate_policies(records, policies)
    write_json(Path(args.json_out), compact_comparison(comparison))
    write_markdown(compact_comparison(comparison), Path(args.md_out))
    print(json.dumps({"records": len(records), "policies": len(policies), "json_out": args.json_out}, indent=2))


if __name__ == "__main__":
    main()
