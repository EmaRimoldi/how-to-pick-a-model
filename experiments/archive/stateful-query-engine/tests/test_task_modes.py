from __future__ import annotations

from benchmarks.stateful_query_engine.generators.workload_gen import generate_trace
from vao.task_modes import single_family_instance_overrides, task_mode_from_instance_overrides, trace_observable_summary


def test_single_family_instance_overrides_round_trip() -> None:
    overrides = single_family_instance_overrides(
        "range_local_scans",
        seed=123,
        traces_per_family=2,
        trace_length=64,
    )
    assert overrides["families"] == ["range_local_scans"]
    assert overrides["seed"] == 123
    assert overrides["traces_per_family"] == 2
    assert task_mode_from_instance_overrides(overrides) == "range_local_scans"


def test_trace_observable_summary_has_expected_fields() -> None:
    trace = generate_trace(
        family="topk_stress",
        seed=42,
        length=48,
        initial_size=80,
        key_space=500,
        value_max=100,
        profile="hard_optimization",
    )
    summary = trace_observable_summary(trace)
    assert summary["task_mode_true"] == "topk_stress"
    assert summary["operation_count"] == 48
    assert 0.0 <= summary["query_ratio"] <= 1.0
    assert 0.0 <= summary["update_ratio"] <= 1.0
    assert summary["mean_range_width"] >= 0.0
    assert summary["initial_size"] == 80
