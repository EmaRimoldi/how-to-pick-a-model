from __future__ import annotations

from pathlib import Path

from vao.logging_utils import append_jsonl
from vao.schemas import BranchEvaluation, StepRecord
from vao.taxonomy import MODES
from vao.training.build_routing_dataset import build_records


def test_dataset_generation_from_toy_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    parent_dir = run_dir / "steps" / "step_0000" / "branches" / "layout"
    parent_dir.mkdir(parents=True)
    parent_dir.joinpath("parent_solution.py").write_text("class CandidateQueryEngine:\n    pass\n", encoding="utf-8")
    branches = []
    for index, mode in enumerate(MODES):
        branches.append(
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
        )
    record = StepRecord(
        run_id="toy",
        profile_id="hard_optimization",
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
    dataset = build_records([run_dir])
    assert len(dataset) == 1
    assert dataset[0].productive_mode_top1 == "micro"
