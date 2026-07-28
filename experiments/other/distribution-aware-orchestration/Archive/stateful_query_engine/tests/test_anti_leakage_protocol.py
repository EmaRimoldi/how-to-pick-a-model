from __future__ import annotations

from pathlib import Path

import pytest

from vao.logging_utils import read_jsonl, write_json
from vao.orchestrator import run_single
from vao.records import load_step_records
from vao.schemas import BranchEvaluation
from vao.validate_run import validate_run
from vao.visibility import summarize_history_for_prompt


def test_top1_visibility_does_not_promote_best_counterfactual(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    losses = {
        "layout": 0.7,
        "indexing": 0.1,
        "topk": 0.8,
        "caching": 0.5,
        "summaries": 0.9,
        "micro": 1.0,
    }

    def fake_evaluate_solution(solution_path: Path, profile_id: str, timeout_seconds: int, out_path: Path, **kwargs: object) -> BranchEvaluation:
        run_id = str(kwargs.get("run_id", ""))
        declared_mode = str(kwargs.get("declared_mode", "micro"))
        if run_id == "baseline":
            loss = 1.0
            declared_mode = "micro"
        else:
            loss = losses[declared_mode]
        result = BranchEvaluation(
            branch_index=int(kwargs.get("branch_index", 0)),
            primary_mode=str(kwargs.get("primary_mode", declared_mode)),
            secondary_modes=list(kwargs.get("secondary_modes", [])),
            declared_mode=declared_mode,
            inferred_mode=str(kwargs.get("inferred_mode", declared_mode)),
            source_hash="hash-" + declared_mode,
            source_parent_hash=kwargs.get("source_parent_hash"),
            file_path=str(solution_path),
            correctness=True,
            latent_loss=loss,
            family_losses={"fake": loss},
            raw_verifier_path=str(out_path.parent / "fake_raw"),
        )
        write_json(out_path, result)
        return result

    monkeypatch.setattr("vao.orchestrator.evaluate_solution", fake_evaluate_solution)
    config = {
        "experiment": {
            "name": "anti_leakage",
            "visibility_regime": "top1_only",
            "modes": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
            "steps": 2,
            "wall_budget_seconds": 300,
            "branch_timeout_seconds": 30,
            "incorrect_penalty": -1.0,
        },
        "benchmark": {
            "template_path": "benchmarks/stateful_query_engine/solution_template.py",
            "profiles": ["hard_optimization"],
        },
        "models": {"include": ["leakage_probe"]},
        "output": {"root": str(tmp_path / "runs")},
    }
    run_dir = run_single(
        config,
        "leakage_probe",
        {"adapter": "leakage_probe", "model_id": "leakage-probe-v1"},
        "hard_optimization",
        run_id="anti_leakage_probe",
    )
    rows = read_jsonl(run_dir / "evaluations.jsonl")
    assert len(rows) == 2
    step0 = rows[0]
    assert step0["selected_mode"] == "caching"
    best_mode = min(step0["branches"], key=lambda branch: branch["latent_loss"])["declared_mode"]
    assert best_mode == "indexing"
    promoted = [branch["declared_mode"] for branch in step0["branches"] if branch["promoted_as_parent"]]
    assert promoted == ["caching"]
    visible = [branch["declared_mode"] for branch in step0["branches"] if branch["selected_as_visible"]]
    assert visible == ["caching"]

    step1_snapshot = rows[1]["parsed_model_output_json"]["visible_history_snapshot"]
    previous_step_visible = [row for row in step1_snapshot if row["step"] == 0][0]
    visible_branch_modes = [branch["declared_mode"] for branch in previous_step_visible["branches"]]
    assert visible_branch_modes == ["caching"]
    assert "best_counterfactual" not in summarize_history_for_prompt(load_step_records(run_dir))

    validation = validate_run(run_dir)
    assert validation["passed"], validation


def test_cb_all_branches_with_fixed_mode_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_evaluate_solution(solution_path: Path, profile_id: str, timeout_seconds: int, out_path: Path, **kwargs: object) -> BranchEvaluation:
        declared_mode = str(kwargs.get("declared_mode", "micro"))
        loss_by_mode = {
            "layout": 0.7,
            "indexing": 0.2,
            "topk": 0.8,
            "caching": 0.5,
            "summaries": 1.2,
            "micro": 0.9,
        }
        loss = 1.0 if kwargs.get("run_id") == "baseline" else loss_by_mode[declared_mode]
        result = BranchEvaluation(
            branch_index=int(kwargs.get("branch_index", 0)),
            primary_mode=str(kwargs.get("primary_mode", declared_mode)),
            secondary_modes=list(kwargs.get("secondary_modes", [])),
            declared_mode=declared_mode,
            inferred_mode=str(kwargs.get("inferred_mode", declared_mode)),
            source_hash="hash-" + declared_mode,
            source_parent_hash=kwargs.get("source_parent_hash"),
            file_path=str(solution_path),
            correctness=True,
            latent_loss=loss,
            family_losses={"fake": loss},
            raw_verifier_path=str(out_path.parent / "fake_raw"),
        )
        write_json(out_path, result)
        return result

    monkeypatch.setattr("vao.orchestrator.evaluate_solution", fake_evaluate_solution)
    config = {
        "experiment": {
            "name": "cb_fixed_mode",
            "feedback_condition": "cb",
            "visibility_regime": "all_branches",
            "selection_policy": "fixed_mode",
            "selected_mode": "micro",
            "ask_post_feedback_distribution": True,
            "modes": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
            "steps": 1,
            "wall_budget_seconds": 300,
            "branch_timeout_seconds": 30,
            "incorrect_penalty": -1.0,
        },
        "benchmark": {
            "template_path": "benchmarks/stateful_query_engine/solution_template.py",
            "profiles": ["hard_optimization"],
        },
        "models": {"include": ["local_stub"]},
        "output": {"root": str(tmp_path / "runs")},
    }
    run_dir = run_single(
        config,
        "local_stub",
        {"adapter": "local_stub", "model_id": "local-stub-v1"},
        "hard_optimization",
        run_id="cb_fixed_mode",
    )
    row = read_jsonl(run_dir / "evaluations.jsonl")[0]
    assert row["feedback_regret_improvement"] is not None
    assert row["feedback_jsd_improvement"] is not None
    assert row["selected_mode_top1"] == "indexing"
    assert row["selected_mode"] == "micro"
    assert [branch["declared_mode"] for branch in row["branches"] if branch["promoted_as_parent"]] == ["micro"]
    assert {branch["declared_mode"] for branch in row["branches"] if branch["selected_as_visible"]} == {
        "layout",
        "indexing",
        "topk",
        "caching",
        "summaries",
        "micro",
    }
    assert set(row["post_feedback_mode_probs"]) == {"layout", "indexing", "topk", "caching", "summaries", "micro"}
    validation = validate_run(run_dir)
    assert validation["passed"], validation


def test_batched_candidate_generation_preserves_six_branch_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_evaluate_solution(solution_path: Path, profile_id: str, timeout_seconds: int, out_path: Path, **kwargs: object) -> BranchEvaluation:
        declared_mode = str(kwargs.get("declared_mode", "micro"))
        loss_by_mode = {
            "layout": 0.8,
            "indexing": 0.3,
            "topk": 0.7,
            "caching": 0.6,
            "summaries": 0.5,
            "micro": 0.9,
        }
        loss = 1.0 if kwargs.get("run_id") == "baseline" else loss_by_mode[declared_mode]
        result = BranchEvaluation(
            branch_index=int(kwargs.get("branch_index", 0)),
            primary_mode=str(kwargs.get("primary_mode", declared_mode)),
            secondary_modes=list(kwargs.get("secondary_modes", [])),
            declared_mode=declared_mode,
            inferred_mode=str(kwargs.get("inferred_mode", declared_mode)),
            source_hash="hash-" + declared_mode,
            source_parent_hash=kwargs.get("source_parent_hash"),
            file_path=str(solution_path),
            correctness=True,
            latent_loss=loss,
            family_losses={"fake": loss},
            raw_verifier_path=str(out_path.parent / "fake_raw"),
        )
        write_json(out_path, result)
        return result

    monkeypatch.setattr("vao.orchestrator.evaluate_solution", fake_evaluate_solution)
    config = {
        "experiment": {
            "name": "batched_local_contract",
            "visibility_regime": "top1_only",
            "candidate_generation": "batched",
            "modes": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
            "steps": 1,
            "wall_budget_seconds": 300,
            "branch_timeout_seconds": 30,
            "incorrect_penalty": -1.0,
        },
        "benchmark": {
            "template_path": "benchmarks/stateful_query_engine/solution_template.py",
            "profiles": ["hard_optimization"],
        },
        "models": {"include": ["local_stub"]},
        "output": {"root": str(tmp_path / "runs")},
    }
    run_dir = run_single(
        config,
        "local_stub",
        {"adapter": "local_stub", "model_id": "local-stub-v1"},
        "hard_optimization",
        run_id="batched_local_contract",
    )
    row = read_jsonl(run_dir / "evaluations.jsonl")[0]
    assert row["parsed_model_output_json"]["candidate_generation"] == "batched_local_stub"
    assert len(row["branches"]) == 6
    assert {branch["source_parent_hash"] for branch in row["branches"]} == {row["parent_solution_hash"]}
    assert [branch["declared_mode"] for branch in row["branches"] if branch["promoted_as_parent"]] == ["indexing"]
    for branch in row["branches"]:
        proposal = Path(branch["file_path"]).parent / "proposal.json"
        assert proposal.exists()
    validation = validate_run(run_dir)
    assert validation["passed"], validation


def test_single_candidate_generation_records_one_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_evaluate_solution(solution_path: Path, profile_id: str, timeout_seconds: int, out_path: Path, **kwargs: object) -> BranchEvaluation:
        declared_mode = str(kwargs.get("declared_mode", "micro"))
        loss_by_mode = {
            "layout": 0.8,
            "indexing": 0.3,
            "topk": 0.7,
            "caching": 0.6,
            "summaries": 0.5,
            "micro": 0.9,
        }
        loss = 1.0 if kwargs.get("run_id") == "baseline" else loss_by_mode[declared_mode]
        result = BranchEvaluation(
            branch_index=int(kwargs.get("branch_index", 0)),
            primary_mode=str(kwargs.get("primary_mode", declared_mode)),
            secondary_modes=list(kwargs.get("secondary_modes", [])),
            declared_mode=declared_mode,
            inferred_mode=str(kwargs.get("inferred_mode", declared_mode)),
            source_hash="hash-" + declared_mode,
            source_parent_hash=kwargs.get("source_parent_hash"),
            file_path=str(solution_path),
            correctness=True,
            latent_loss=loss,
            family_losses={"fake": loss},
            raw_verifier_path=str(out_path.parent / "fake_raw"),
        )
        write_json(out_path, result)
        return result

    monkeypatch.setattr("vao.orchestrator.evaluate_solution", fake_evaluate_solution)
    config = {
        "experiment": {
            "name": "single_local_contract",
            "visibility_regime": "top1_only",
            "candidate_generation": "single",
            "modes": ["layout", "indexing", "topk", "caching", "summaries", "micro"],
            "steps": 1,
            "wall_budget_seconds": 300,
            "branch_timeout_seconds": 30,
            "incorrect_penalty": -1.0,
        },
        "benchmark": {
            "template_path": "benchmarks/stateful_query_engine/solution_template.py",
            "profiles": ["hard_optimization"],
        },
        "models": {"include": ["local_stub"]},
        "output": {"root": str(tmp_path / "runs")},
    }
    run_dir = run_single(
        config,
        "local_stub",
        {"adapter": "local_stub", "model_id": "local-stub-v1"},
        "hard_optimization",
        run_id="single_local_contract",
    )
    row = read_jsonl(run_dir / "evaluations.jsonl")[0]
    assert row["parsed_model_output_json"]["candidate_generation"] == "single_local_stub"
    assert len(row["branches"]) == 1
    assert row["selected_mode_top1"] == row["selected_mode"] == "indexing"
    assert row["branches"][0]["declared_mode"] == "indexing"
    validation = validate_run(run_dir)
    assert validation["passed"], validation
