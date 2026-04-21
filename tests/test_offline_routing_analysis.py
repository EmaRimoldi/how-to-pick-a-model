from __future__ import annotations

import json
from pathlib import Path

from vao.analysis.dataset_audit import audit_dataset
from vao.analysis.replay_routing import AlwaysModeRouter, OriginalTeacherRouter, evaluate_policy
from vao.analysis.routing_choice_visuals import summarize_dataset
from vao.logging_utils import write_json
from vao.schemas import BranchEvaluation, StepRecord
from vao.taxonomy import MODES
from vao.training.offline_routing_experiments import run_offline_experiments
from vao.training.routing_features import record_to_text, structured_features_from_record


def test_dataset_audit_and_feature_extraction(tmp_path: Path) -> None:
    dataset = _toy_dataset(tmp_path)
    audit = audit_dataset(dataset)
    assert audit["total_examples"] == 6
    assert audit["examples_per_profile"]["paper_development"] == 6
    assert audit["examples_per_productive_mode"]["indexing"] >= 1
    record = json.loads(dataset.read_text(encoding="utf-8").splitlines()[0])
    assert "PROFILE" in record_to_text(record)
    features = structured_features_from_record(record)
    assert features["has_bisect"] == 1.0


def test_replay_evaluator_scores_policies(tmp_path: Path) -> None:
    dataset = _toy_dataset(tmp_path)
    records = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    original = evaluate_policy(records, OriginalTeacherRouter())
    always_indexing = evaluate_policy(records, AlwaysModeRouter("indexing"))
    assert original["record_count"] == 6
    assert always_indexing["mean_top1_regret"] >= 0.0
    assert "mean_visible_best_loss_logged_replay" in always_indexing


def test_routing_choice_summary_counts_verified_best(tmp_path: Path) -> None:
    dataset = _toy_dataset(tmp_path)
    summary = summarize_dataset("toy", dataset)
    assert summary["record_count"] == 6
    assert summary["correct_by_verified_best"] == 2
    assert summary["incorrect_by_verified_best"] == 4
    assert summary["selected_mode_counts"]["indexing"] == 6
    assert summary["verified_best_mode_counts"]["indexing"] == 2


def test_offline_leaderboard_generation(tmp_path: Path) -> None:
    dataset = _toy_dataset(tmp_path)
    result = run_offline_experiments(
        {
            "offline_routing": {
                "dataset": str(dataset),
                "output_dir": str(tmp_path / "training"),
                "previous_student_model": str(tmp_path / "missing.pkl"),
                "train_summary_out": str(tmp_path / "train.json"),
                "eval_summary_out": str(tmp_path / "eval.json"),
                "model_comparison_out": str(tmp_path / "comparison.json"),
                "leaderboard_out": str(tmp_path / "leaderboard.json"),
                "leaderboard_md_out": str(tmp_path / "leaderboard.md"),
                "max_source_chars": 1000,
            }
        }
    )
    assert result["train_summary"]["status"] == "completed"
    assert result["leaderboard"]["entries"]
    assert (tmp_path / "training" / "model.pkl").exists()


def _toy_dataset(tmp_path: Path) -> Path:
    rows = []
    dataset = tmp_path / "routing.jsonl"
    for index, target in enumerate(["indexing", "layout", "indexing", "topk", "layout", "micro"]):
        step_path = _toy_step(tmp_path, index, target)
        gains = {mode: -0.1 for mode in MODES}
        gains[target] = 1.0
        pstar = {mode: 0.0 for mode in MODES}
        pstar[target] = 1.0
        original = {mode: 1 / len(MODES) for mode in MODES}
        original["indexing"] = 0.5
        original = {mode: value / sum(original.values()) for mode, value in original.items()}
        rows.append(
            {
                "run_id": "toy",
                "profile_id": "paper_development",
                "model_id": "teacher",
                "step": index,
                "input": {
                    "profile_summary": {"profile_id": "paper_development"},
                    "current_solution_hash": f"h{index}",
                    "current_solution_source": "import bisect\nclass CandidateQueryEngine:\n    pass\n",
                    "visible_history": [],
                    "recent_decision_history": [],
                    "full_history_summary": "",
                },
                "productive_mode_top1": target,
                "productive_mode_distribution": pstar,
                "verified_gain_per_mode": gains,
                "original_mode_probs": original,
                "original_top1_regret": max(gains.values()) - gains["indexing"],
                "source_step_record_path": str(step_path),
            }
        )
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return dataset


def _toy_step(tmp_path: Path, index: int, target: str) -> Path:
    branches = []
    for branch_index, mode in enumerate(MODES):
        branches.append(
            BranchEvaluation(
                branch_index=branch_index,
                primary_mode=mode,
                declared_mode=mode,
                inferred_mode=mode,
                source_hash=f"{index}-{mode}",
                source_parent_hash=f"parent-{index}",
                file_path=str(tmp_path / f"{index}-{mode}.py"),
                correctness=True,
                latent_loss=0.1 if mode == target else 1.0 + branch_index,
                gain=1.0 if mode == target else -0.1,
                selected_as_visible=mode == "indexing",
                promoted_as_parent=mode == "indexing",
            )
        )
    step = StepRecord(
        run_id="toy",
        profile_id="paper_development",
        model_id="teacher",
        step=index,
        current_solution_hash=f"parent-{index}",
        parent_solution_hash=f"parent-{index}",
        parent_latent_loss=1.1,
        mode_probs={mode: (0.5 if mode == "indexing" else 0.1) for mode in MODES},
        mode_ranking=["indexing", "layout", "topk", "caching", "summaries", "micro"],
        selected_mode_top1="indexing",
        selected_mode="indexing",
        selected_branch=str(tmp_path),
        candidate_batch_id=f"batch-{index}",
        visibility_regime="top1_only",
        branches=branches,
        residual_steps=0,
    )
    path = tmp_path / f"step_{index:04d}.json"
    write_json(path, step)
    return path
