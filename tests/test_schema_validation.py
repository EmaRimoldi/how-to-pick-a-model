from __future__ import annotations

import pytest

from vao.schemas import BranchEvaluation, ModeDistribution, StepRecord
from vao.taxonomy import MODES


def test_mode_distribution_validates_ranking() -> None:
    probs = {mode: 1 / 6 for mode in MODES}
    dist = ModeDistribution(mode_probs=probs, mode_ranking=list(MODES))
    assert dist.top_mode in MODES
    with pytest.raises(ValueError):
        ModeDistribution(mode_probs=probs, mode_ranking=["layout"])


def test_step_record_schema() -> None:
    branches = [
        BranchEvaluation(
            branch_index=index,
            primary_mode=mode,
            declared_mode=mode,
            inferred_mode=mode,
            source_hash=f"hash-{mode}",
            file_path=f"/tmp/{mode}.py",
            correctness=True,
            latent_loss=1.0,
        )
        for index, mode in enumerate(MODES)
    ]
    record = StepRecord(
        run_id="r",
        profile_id="paper_development",
        model_id="m",
        step=0,
        current_solution_hash="parent",
        parent_solution_hash="parent",
        mode_probs={mode: 1 / 6 for mode in MODES},
        mode_ranking=list(MODES),
        selected_mode_top1="layout",
        selected_mode="layout",
        selected_branch="/tmp/layout",
        candidate_batch_id="batch",
        visibility_regime="top1_only",
        branches=branches,
        residual_steps=0,
    )
    assert record.branches[0].primary_mode == "layout"
