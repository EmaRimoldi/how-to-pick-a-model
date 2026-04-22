from __future__ import annotations

from pathlib import Path

import yaml

from benchmarks.stateful_query_engine.harness.run_benchmark import load_instance_config
from vao.analysis.profile_split_audit import build_audit
from vao.logging_utils import append_jsonl
from vao.profile_splits import load_profile_splits, summarize_profile_splits
from vao.schemas import BranchEvaluation, StepRecord
from vao.taxonomy import MODES
from vao.training.build_routing_dataset import build_records
from vao.training.routing_features import record_to_text, structured_features_from_record


def test_active_dev_holdout_profiles_are_disjoint_and_known() -> None:
    splits = load_profile_splits(Path("configs/profiles.yaml"))
    benchmark_profiles = load_instance_config()["profiles"]
    summary = summarize_profile_splits(splits, benchmark_profiles)

    assert summary["dev_holdout_overlap"] == []
    assert summary["dev_holdout_seed_overlap"] == []
    assert summary["missing_from_benchmark"]["dev"] == []
    assert summary["missing_from_benchmark"]["holdout"] == []
    assert len(splits["dev"]) == 3
    assert len(splits["holdout"]) == 3


def test_paper_experiment_configs_use_intended_splits() -> None:
    splits = load_profile_splits(Path("configs/profiles.yaml"))
    dev_config = yaml.safe_load(Path("configs/paper_dev_model_comparison.yaml").read_text(encoding="utf-8"))
    holdout_config = yaml.safe_load(Path("configs/paper_holdout_final_eval.yaml").read_text(encoding="utf-8"))

    assert dev_config["benchmark"]["profiles"] == splits["dev"]
    assert holdout_config["benchmark"]["profiles"] == splits["holdout"]


def test_profile_split_audit_reports_configured_profiles() -> None:
    audit = build_audit(Path("configs/profiles.yaml"))
    assert audit["counts"]["dev"] == 3
    assert audit["counts"]["holdout"] == 3
    assert "hard_balanced_dev" in audit["profile_details"]
    assert "hard_balanced_holdout" in audit["profile_details"]


def test_build_routing_dataset_can_exclude_holdout(tmp_path: Path) -> None:
    splits_path = tmp_path / "profiles.yaml"
    splits_path.write_text(
        yaml.safe_dump({"profiles": {"dev": ["hard_balanced_dev"], "holdout": ["hard_balanced_holdout"]}}),
        encoding="utf-8",
    )
    root = tmp_path / "runs"
    _write_toy_run(root / "dev_run", "hard_balanced_dev")
    _write_toy_run(root / "holdout_run", "hard_balanced_holdout")

    splits = load_profile_splits(splits_path)
    all_records = build_records([root], profile_splits=splits)
    trainable_records = build_records([root], profile_splits=splits, exclude_holdout=True)

    assert {record.profile_id for record in all_records} == {"hard_balanced_dev", "hard_balanced_holdout"}
    assert [record.profile_id for record in trainable_records] == ["hard_balanced_dev"]
    assert trainable_records[0].profile_split == "dev"
    assert trainable_records[0].input["profile_split"] == "dev"

    dumped = trainable_records[0].model_dump(mode="json")
    assert "PROFILE_SPLIT dev" in record_to_text(dumped)
    assert structured_features_from_record(dumped)["profile_split"] == "dev"


def _write_toy_run(run_dir: Path, profile_id: str) -> None:
    parent_dir = run_dir / "steps" / "step_0000" / "branches" / "layout"
    parent_dir.mkdir(parents=True)
    parent_dir.joinpath("parent_solution.py").write_text("class CandidateQueryEngine:\n    pass\n", encoding="utf-8")
    branches = [
        BranchEvaluation(
            branch_index=index,
            primary_mode=mode,
            declared_mode=mode,
            inferred_mode=mode,
            source_hash=f"h-{mode}",
            file_path=str(parent_dir / f"{mode}.py"),
            correctness=True,
            latent_loss=1.0 - index * 0.01,
            gain=index * 0.01,
            promoted_as_parent=mode == "layout",
            selected_as_visible=mode == "layout",
        )
        for index, mode in enumerate(MODES)
    ]
    record = StepRecord(
        run_id=run_dir.name,
        profile_id=profile_id,
        model_id="local",
        step=0,
        current_solution_hash="parent",
        parent_solution_hash="parent",
        mode_probs={mode: 1 / 6 for mode in MODES},
        mode_ranking=list(MODES),
        selected_mode_top1="layout",
        selected_mode="layout",
        selected_branch=str(parent_dir),
        candidate_batch_id="batch",
        visibility_regime="top1_only",
        branches=branches,
        residual_steps=0,
    )
    append_jsonl(run_dir / "evaluations.jsonl", record)
