"""Correctness verifier for stateful query engine candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

from benchmarks.stateful_query_engine.generators.workload_gen import WorkloadTrace
from benchmarks.stateful_query_engine.harness.run_trace import run_trace


EngineFactory = Callable[[dict[int, int]], object]


@dataclass
class CorrectnessResult:
    passed: bool
    trace_count: int
    query_output_count: int
    first_divergence: dict | None = None
    family_results: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def verify_correctness(
    candidate_factory: EngineFactory,
    reference_factory: EngineFactory,
    traces: list[WorkloadTrace],
) -> CorrectnessResult:
    total_outputs = 0
    family_results: dict[str, dict] = {}
    for trace in traces:
        ref = run_trace(reference_factory, trace)
        cand = run_trace(candidate_factory, trace)
        total_outputs += len(ref.observable_outputs)
        family = family_results.setdefault(
            trace.family,
            {"trace_count": 0, "query_output_count": 0, "passed": True},
        )
        family["trace_count"] += 1
        family["query_output_count"] += len(ref.observable_outputs)
        divergence = first_divergence(trace, ref.observable_outputs, cand.observable_outputs)
        if divergence is not None:
            family["passed"] = False
            return CorrectnessResult(
                passed=False,
                trace_count=len(traces),
                query_output_count=total_outputs,
                first_divergence=divergence,
                family_results=family_results,
            )
    return CorrectnessResult(
        passed=True,
        trace_count=len(traces),
        query_output_count=total_outputs,
        first_divergence=None,
        family_results=family_results,
    )


def first_divergence(
    trace: WorkloadTrace,
    reference_outputs: list[dict],
    candidate_outputs: list[dict],
) -> dict | None:
    max_len = max(len(reference_outputs), len(candidate_outputs))
    for output_index in range(max_len):
        ref = reference_outputs[output_index] if output_index < len(reference_outputs) else None
        cand = candidate_outputs[output_index] if output_index < len(candidate_outputs) else None
        if ref != cand:
            op_index = ref.get("index") if isinstance(ref, dict) else cand.get("index")
            operation = (
                trace.operations[op_index]
                if isinstance(op_index, int) and 0 <= op_index < len(trace.operations)
                else None
            )
            return {
                "trace_id": trace.trace_id,
                "family": trace.family,
                "query_output_index": output_index,
                "operation_index": op_index,
                "operation": operation,
                "expected": ref,
                "actual": cand,
            }
    return None

