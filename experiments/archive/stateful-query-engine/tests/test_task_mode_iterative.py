from __future__ import annotations

import math

from vao.analysis.oracle_family_iterative import (
    Trajectory,
    _allocated_prefix_wall_seconds,
    _prefix_summary_frame,
)
from vao.schemas import BranchEvaluation, StepRecord
from vao.taxonomy import MODES


def _branch(mode: str, *, loss: float, elapsed: float, promoted: bool = False) -> BranchEvaluation:
    return BranchEvaluation(
        branch_index=MODES.index(mode),
        primary_mode=mode,
        declared_mode=mode,
        inferred_mode=mode,
        source_hash=f"hash-{mode}",
        source_parent_hash="parent-hash",
        file_path="solution.py",
        correctness=math.isfinite(loss),
        latent_loss=loss,
        gain=0.0,
        promoted_as_parent=promoted,
        elapsed_wall_seconds=elapsed,
    )


def _step(step: int, *, selected_mode: str, selected_loss: float, other_loss: float, per_branch_elapsed: float) -> StepRecord:
    branches = []
    for mode in MODES:
        loss = selected_loss if mode == selected_mode else other_loss
        branches.append(_branch(mode, loss=loss, elapsed=per_branch_elapsed, promoted=(mode == selected_mode)))
    return StepRecord(
        run_id="demo-run",
        profile_id="hard_optimization",
        model_id="demo-model",
        model_alias="demo-model",
        task_mode_true="topk_stress",
        task_mode_source="oracle_family",
        task_mode_split="pilot",
        instance_seed=123,
        step=step,
        current_solution_hash=f"current-{step}",
        parent_solution_hash=f"parent-{step}",
        parent_latent_loss=1.0,
        mode_probs={mode: (1.0 if mode == selected_mode else 0.0) for mode in MODES},
        mode_ranking=[selected_mode] + [mode for mode in MODES if mode != selected_mode],
        selected_mode_top1=selected_mode,
        selected_mode=selected_mode,
        selection_policy="top1",
        selected_mode_reason="test",
        selected_branch=selected_mode,
        candidate_batch_id=f"batch-{step}",
        visibility_regime="top1_only",
        branches=branches,
        residual_steps=2 - step,
    )


def test_prefix_summary_distinguishes_terminal_and_anytime_success() -> None:
    trajectory = Trajectory(
        run_dir=None,  # type: ignore[arg-type]
        run_id="demo-run",
        split="pilot",
        model_id="demo-model",
        model_alias="demo-model",
        task_mode_true="topk_stress",
        instance_seed=123,
        baseline_loss=1.0,
        total_elapsed_wall_seconds=30.0,
        completed=True,
        records=[
            _step(0, selected_mode="topk", selected_loss=0.80, other_loss=0.95, per_branch_elapsed=1.0),
            _step(1, selected_mode="micro", selected_loss=0.95, other_loss=0.96, per_branch_elapsed=2.0),
        ],
    )

    terminal = _prefix_summary_frame([trajectory], horizon=2, success_kind="terminal", tau=0.10)
    anytime = _prefix_summary_frame([trajectory], horizon=2, success_kind="anytime", tau=0.10)

    assert terminal.iloc[0]["success_prob"] == 0.0
    assert anytime.iloc[0]["success_prob"] == 1.0
    assert math.isclose(float(anytime.iloc[0]["mean_relative_improvement"]), 0.20)
    assert math.isclose(float(terminal.iloc[0]["median_cost"]), 30.0)


def test_prefix_wall_seconds_are_allocated_by_branch_time_proxy() -> None:
    trajectory = Trajectory(
        run_dir=None,  # type: ignore[arg-type]
        run_id="demo-run",
        split="pilot",
        model_id="demo-model",
        model_alias="demo-model",
        task_mode_true="range_local_scans",
        instance_seed=123,
        baseline_loss=1.0,
        total_elapsed_wall_seconds=30.0,
        completed=True,
        records=[
            _step(0, selected_mode="layout", selected_loss=0.90, other_loss=0.92, per_branch_elapsed=1.0),
            _step(1, selected_mode="caching", selected_loss=0.85, other_loss=0.90, per_branch_elapsed=2.0),
        ],
    )

    prefix_h1 = _allocated_prefix_wall_seconds(trajectory, horizon=1)
    prefix_h2 = _allocated_prefix_wall_seconds(trajectory, horizon=2)

    assert math.isclose(prefix_h1, 10.0)
    assert math.isclose(prefix_h2, 30.0)
