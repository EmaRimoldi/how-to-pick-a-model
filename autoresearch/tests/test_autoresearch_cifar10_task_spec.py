from __future__ import annotations

from pathlib import Path

from autoresearch.benchmark.cifar10.task_spec import (
    classify_edit_mode,
    profile_summary,
    single_workload_instance_overrides,
    validate_solution_source,
)


def test_profile_summary_exposes_workload_features() -> None:
    summary = profile_summary(
        "autoresearch_cifar10",
        single_workload_instance_overrides("mlp_flat", seed=99, max_train_steps=7),
    )
    assert summary["workload_id"] == "mlp_flat"
    assert summary["task_mode_true"] == "mlp_flat"
    assert summary["architecture_name"] == "flat_mlp"
    assert summary["max_train_steps"] == 7
    assert "layout" in summary["action_mode_aliases"]


def test_classifier_maps_learning_rate_change_to_topk_mode() -> None:
    source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
    modified = source.replace("LEARNING_RATE = 5e-4", "LEARNING_RATE = 1e-3")
    primary, secondary, details = classify_edit_mode(source, modified)
    assert primary == "topk"
    assert secondary == []
    assert details["scores"]["topk"] > 0.0


def test_validate_solution_source_rejects_banned_imports() -> None:
    source = Path("autoresearch/benchmark/cifar10/solution_template.py").read_text(encoding="utf-8")
    invalid = "import subprocess\n" + source
    result = validate_solution_source(invalid)
    assert result["passed"] is False
    assert any(item.startswith("banned_import:subprocess") for item in result["errors"])
