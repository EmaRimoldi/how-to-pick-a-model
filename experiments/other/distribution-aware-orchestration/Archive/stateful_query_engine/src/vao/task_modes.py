"""Task-mode helpers for oracle-family and future discovered-mode experiments."""

from __future__ import annotations

import statistics
from typing import Any

from benchmarks.stateful_query_engine.generators.workload_gen import ALL_FAMILIES, QUERY_OPS, UPDATE_OPS, WorkloadTrace


TASK_MODES = list(ALL_FAMILIES)
TASK_MODE_SET = set(TASK_MODES)


def validate_task_mode(mode: str) -> str:
    if mode not in TASK_MODE_SET:
        raise ValueError(f"Unknown task mode {mode!r}; expected one of {TASK_MODES}")
    return mode


def task_mode_from_instance_overrides(overrides: dict[str, Any] | None) -> str | None:
    if not isinstance(overrides, dict):
        return None
    families = overrides.get("families")
    if not isinstance(families, list) or len(families) != 1:
        return None
    candidate = families[0]
    if not isinstance(candidate, str) or candidate not in TASK_MODE_SET:
        return None
    return candidate


def single_family_instance_overrides(
    task_mode: str,
    *,
    seed: int | None = None,
    traces_per_family: int = 1,
    initial_size: int | None = None,
    key_space: int | None = None,
    trace_length: int | None = None,
    repetitions: int | None = None,
    warmup_prefix: int | None = None,
    value_max: int | None = None,
) -> dict[str, Any]:
    validate_task_mode(task_mode)
    overrides: dict[str, Any] = {
        "families": [task_mode],
        "traces_per_family": int(traces_per_family),
    }
    optional = {
        "seed": seed,
        "initial_size": initial_size,
        "key_space": key_space,
        "trace_length": trace_length,
        "repetitions": repetitions,
        "warmup_prefix": warmup_prefix,
        "value_max": value_max,
    }
    for key, value in optional.items():
        if value is not None:
            overrides[key] = int(value)
    return overrides


def trace_observable_summary(trace: WorkloadTrace) -> dict[str, Any]:
    op_count = len(trace.operations)
    counts = {name: 0 for name in sorted(QUERY_OPS | UPDATE_OPS)}
    range_widths: list[int] = []
    topk_ks: list[int] = []
    centers: list[float] = []

    for operation in trace.operations:
        name = str(operation.get("op"))
        if name in counts:
            counts[name] += 1
        if name in {"range_sum", "aggregate_count", "top_k"}:
            lo = int(operation.get("lo", 0))
            hi = int(operation.get("hi", lo))
            range_widths.append(max(0, hi - lo + 1))
            centers.append((lo + hi) / 2.0)
        elif name in {"get", "put", "delete"}:
            centers.append(float(int(operation.get("key", 0))))
        if name == "top_k":
            topk_ks.append(int(operation.get("k", 0)))

    query_count = sum(counts[name] for name in QUERY_OPS)
    update_count = sum(counts[name] for name in UPDATE_OPS)
    mean_center_jump = 0.0
    if len(centers) >= 2:
        mean_center_jump = statistics.fmean(abs(centers[index] - centers[index - 1]) for index in range(1, len(centers)))

    return {
        "trace_id": trace.trace_id,
        "task_mode_true": trace.family,
        "operation_count": op_count,
        "query_ratio": query_count / op_count if op_count else 0.0,
        "update_ratio": update_count / op_count if op_count else 0.0,
        "get_ratio": counts["get"] / op_count if op_count else 0.0,
        "put_ratio": counts["put"] / op_count if op_count else 0.0,
        "delete_ratio": counts["delete"] / op_count if op_count else 0.0,
        "range_sum_ratio": counts["range_sum"] / op_count if op_count else 0.0,
        "aggregate_count_ratio": counts["aggregate_count"] / op_count if op_count else 0.0,
        "topk_ratio": counts["top_k"] / op_count if op_count else 0.0,
        "mean_range_width": statistics.fmean(range_widths) if range_widths else 0.0,
        "max_range_width": max(range_widths) if range_widths else 0,
        "mean_topk_k": statistics.fmean(topk_ks) if topk_ks else 0.0,
        "mean_center_jump": mean_center_jump,
        "initial_size": len(trace.initial_items),
    }
