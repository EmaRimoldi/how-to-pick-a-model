"""Trace execution utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from benchmarks.stateful_query_engine.generators.workload_gen import QUERY_OPS, WorkloadTrace


EngineFactory = Callable[[dict[int, int]], object]


@dataclass
class TraceRunResult:
    trace_id: str
    family: str
    observable_outputs: list[dict[str, Any]]
    op_latencies_ns: list[int] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    operation_count: int = 0


def run_trace(
    engine_factory: EngineFactory,
    trace: WorkloadTrace,
    *,
    collect_timings: bool = False,
) -> TraceRunResult:
    engine = engine_factory(dict(trace.initial_items))
    outputs: list[dict[str, Any]] = []
    latencies: list[int] = []
    start = time.perf_counter()
    for index, operation in enumerate(trace.operations):
        op_start = time.perf_counter_ns()
        result = apply_operation(engine, operation)
        op_elapsed = time.perf_counter_ns() - op_start
        if collect_timings:
            latencies.append(op_elapsed)
        if operation["op"] in QUERY_OPS:
            outputs.append(
                {
                    "index": index,
                    "op": operation["op"],
                    "result": normalize_output(result),
                }
            )
    elapsed = time.perf_counter() - start
    return TraceRunResult(
        trace_id=trace.trace_id,
        family=trace.family,
        observable_outputs=outputs,
        op_latencies_ns=latencies,
        elapsed_seconds=elapsed,
        operation_count=len(trace.operations),
    )


def apply_operation(engine: object, operation: dict[str, Any]) -> Any:
    op_name = operation["op"]
    if op_name == "put":
        return engine.put(operation["key"], operation["value"])
    if op_name == "delete":
        return engine.delete(operation["key"])
    if op_name == "get":
        return engine.get(operation["key"])
    if op_name == "range_sum":
        return engine.range_sum(operation["lo"], operation["hi"])
    if op_name == "top_k":
        return engine.top_k(operation["lo"], operation["hi"], operation["k"])
    if op_name == "aggregate_count":
        return engine.aggregate_count(operation["lo"], operation["hi"])
    raise ValueError(f"Unknown operation: {op_name}")


def normalize_output(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [normalize_output(item) for item in value]
    return value

