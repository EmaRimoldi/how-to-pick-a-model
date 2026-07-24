from __future__ import annotations

from pathlib import Path

from vao.agents.autoresearch_local_stub_adapter import AutoResearchLocalStubAdapter
from vao.agents.base import AgentState
from vao.taxonomy import MODES


def test_autoresearch_local_stub_emits_batch_candidates(tmp_path: Path) -> None:
    parent_source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
    branch_dirs: dict[str, Path] = {}
    for mode in MODES:
        branch_dir = tmp_path / mode
        branch_dir.mkdir(parents=True)
        (branch_dir / "parent_solution.py").write_text(parent_source, encoding="utf-8")
        (branch_dir / "proposed_solution.py").write_text(parent_source, encoding="utf-8")
        branch_dirs[mode] = branch_dir

    adapter = AutoResearchLocalStubAdapter()
    state = AgentState(
        run_id="r0",
        profile_id="autoresearch_cifar10",
        model_id="autoresearch-local-stub",
        step=0,
        current_solution_path=tmp_path / "solution.py",
        current_solution_source=parent_source,
        visible_history=[],
        profile_summary={
            "task_mode_true": "cnn_compact",
            "workload_id": "cnn_compact",
            "train_subset_size": 1024,
            "val_subset_size": 512,
            "label_noise_rate": 0.0,
            "imbalance_ratio": 1.0,
            "max_train_steps": 4,
            "action_mode_aliases": {},
        },
        residual_steps=2,
        residual_wall_seconds=None,
        visibility_regime="top1_only",
        metadata={"prompt_template": "autoresearch_program.txt"},
    )

    distribution, proposals = adapter.propose_step_batch(state, branch_dirs)
    assert set(distribution.mode_probs) == set(MODES)
    assert distribution.top_mode in MODES
    assert set(proposals) == set(MODES)
    assert proposals["topk"].changed is True
    assert (branch_dirs["topk"] / "model_edit.json").exists()


def test_autoresearch_local_stub_emits_single_candidate(tmp_path: Path) -> None:
    parent_source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
    branch_dirs: dict[str, Path] = {}
    for mode in MODES:
        branch_dir = tmp_path / mode
        branch_dir.mkdir(parents=True)
        (branch_dir / "parent_solution.py").write_text(parent_source, encoding="utf-8")
        (branch_dir / "proposed_solution.py").write_text(parent_source, encoding="utf-8")
        branch_dirs[mode] = branch_dir

    adapter = AutoResearchLocalStubAdapter()
    state = AgentState(
        run_id="r0",
        profile_id="autoresearch_cifar10",
        model_id="autoresearch-local-stub",
        step=0,
        current_solution_path=tmp_path / "solution.py",
        current_solution_source=parent_source,
        visible_history=[],
        profile_summary={
            "task_mode_true": "cnn_compact",
            "workload_id": "cnn_compact",
            "train_subset_size": 50000,
            "val_subset_size": 10000,
            "label_noise_rate": 0.0,
            "imbalance_ratio": 1.0,
            "max_train_steps": 500,
            "action_mode_aliases": {},
        },
        residual_steps=20,
        residual_wall_seconds=None,
        visibility_regime="top1_only",
        metadata={"prompt_template": "autoresearch_program.txt"},
    )

    distribution, proposal = adapter.propose_step_single(state, branch_dirs)
    assert distribution.top_mode == "summaries"
    assert sum(1 for value in distribution.mode_probs.values() if value > 0.0) == 1
    assert proposal.declared_mode == "summaries"
    assert proposal.parsed_output_json["candidate_generation"] == "single_autoresearch_local_stub"
