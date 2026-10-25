from __future__ import annotations

import pytest

from agent_workflow.baseline_calibration import (
    TrialResult,
    apply_constant_changes,
    attach_improvements,
    build_calibration_plan,
    choose_recommendation,
    extended_baselines,
    extended_edit_panel,
    extract_constant_values,
    load_change_specs,
    summarize_baselines,
)


TRAIN_SOURCE = """
DEPTH = 3
BASE_CHANNELS = 32
CHANNEL_MULT = 2
USE_BATCHNORM = True
DROPOUT_RATE = 0.0
FC_HIDDEN = 128
OPTIMIZER = "adam"
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
MOMENTUM = 0.9
ADAM_BETAS = (0.9, 0.999)
USE_LR_SCHEDULE = True
WARMUP_EPOCHS = 2
LR_DECAY_FACTOR = 0.1
LR_DECAY_EPOCHS = [60, 80]
BATCH_SIZE = 128
NUM_WORKERS = 0
"""


def _result(
    *,
    trial_id: str,
    baseline_id: str = "candidate",
    category: str = "baseline",
    val_bpb: float | None,
    is_baseline: bool = False,
) -> TrialResult:
    return TrialResult(
        id=trial_id,
        baseline_id=baseline_id,
        category=category,
        description="test",
        changes={},
        baseline_changes={},
        edit_changes={},
        is_baseline=is_baseline,
        status="success" if val_bpb is not None else "crash",
        returncode=0 if val_bpb is not None else 1,
        val_bpb=val_bpb,
        total_seconds=1.0,
        training_seconds=1.0,
        total_steps=2,
        evaluator_mode="fixed_steps",
        train_max_steps=2,
        trial_dir="/tmp/trial",
        stdout_path="/tmp/trial/stdout.txt",
        stderr_path="/tmp/trial/stderr.txt",
    )


def test_apply_constant_changes_updates_supported_constants() -> None:
    changed = apply_constant_changes(
        TRAIN_SOURCE,
        {"LEARNING_RATE": 5e-4, "OPTIMIZER": "adamw", "USE_BATCHNORM": False},
    )

    assert "LEARNING_RATE = 0.0005" in changed
    assert "OPTIMIZER = 'adamw'" in changed
    assert "USE_BATCHNORM = False" in changed


def test_apply_constant_changes_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        apply_constant_changes(TRAIN_SOURCE, {"NOT_A_PARAM": 1})


def test_extract_constant_values_parses_literals() -> None:
    values = extract_constant_values(TRAIN_SOURCE)

    assert values["LEARNING_RATE"] == pytest.approx(1e-3)
    assert values["OPTIMIZER"] == "adam"
    assert values["USE_LR_SCHEDULE"] is True
    assert values["ADAM_BETAS"] == (0.9, 0.999)


def test_build_calibration_plan_skips_noop_edits() -> None:
    plan = build_calibration_plan(
        TRAIN_SOURCE,
        baseline_ids={"current_control"},
        edit_ids={"cosine_schedule_on", "cosine_schedule_off"},
        include_current_control=True,
    )

    assert [spec.id for spec in plan] == [
        "current_control__baseline",
        "current_control__scheduler__cosine_schedule_off",
    ]


def test_extended_panel_contains_followup_specs() -> None:
    baseline_ids = {spec.id for spec in extended_baselines()}
    edit_ids = {spec.id for spec in extended_edit_panel()}

    assert "sgd_baseline" in baseline_ids
    assert "shallow_lr_low" in baseline_ids
    assert "lr_1e3_schedule_on" in edit_ids
    assert "depth4_width24" in edit_ids


def test_load_change_specs_from_json(tmp_path) -> None:
    path = tmp_path / "specs.json"
    path.write_text(
        """
[
  {
    "id": "custom",
    "category": "baseline",
    "description": "Custom spec",
    "changes": {"LEARNING_RATE": 0.0005}
  }
]
"""
    )

    specs = load_change_specs(path)

    assert len(specs) == 1
    assert specs[0].id == "custom"
    assert specs[0].changes == {"LEARNING_RATE": 0.0005}


def test_summarize_baselines_passes_multicategory_gate_and_sets_q_star() -> None:
    results = [
        _result(trial_id="candidate__baseline", val_bpb=1.05, is_baseline=True),
        _result(trial_id="candidate__optimizer", category="optimizer_lr", val_bpb=1.00),
        _result(trial_id="candidate__scheduler", category="scheduler", val_bpb=1.01),
        _result(
            trial_id="candidate__capacity",
            category="normalization_capacity",
            val_bpb=1.02,
        ),
    ]
    for index in range(7):
        results.append(
            _result(
                trial_id=f"candidate__fail_{index}",
                category="regularization" if index % 2 else "data_batch",
                val_bpb=1.049,
            )
        )

    results = attach_improvements(results, min_delta=0.005)
    summaries = summarize_baselines(
        results,
        min_delta=0.005,
        min_categories=3,
        min_success_rate=0.10,
        max_success_rate=0.30,
    )
    recommendation = choose_recommendation(
        summaries,
        min_success_rate=0.10,
        max_success_rate=0.30,
    )

    assert len(summaries) == 1
    assert summaries[0].passes_gate is True
    assert summaries[0].winning_categories == [
        "normalization_capacity",
        "optimizer_lr",
        "scheduler",
    ]
    assert summaries[0].success_rate == pytest.approx(0.3)
    assert summaries[0].proposed_q_star == pytest.approx(1.02)
    assert recommendation is summaries[0]
