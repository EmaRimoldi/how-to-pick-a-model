"""Performance evaluator with warm-up, repetitions, and robust aggregation."""

from __future__ import annotations

import statistics
import tracemalloc
from dataclasses import asdict, dataclass, field
from typing import Callable

from benchmarks.stateful_query_engine.generators.workload_gen import WorkloadTrace
from benchmarks.stateful_query_engine.harness.run_trace import run_trace


EngineFactory = Callable[[dict[int, int]], object]


@dataclass
class RepetitionMetrics:
    elapsed_seconds: float
    throughput_ops_per_sec: float
    p95_latency_ns: float
    mean_latency_ns: float
    peak_memory_bytes: int


@dataclass
class TracePerfMetrics:
    trace_id: str
    family: str
    repetitions: list[RepetitionMetrics]
    median_elapsed_seconds: float
    median_throughput_ops_per_sec: float
    median_p95_latency_ns: float
    median_peak_memory_bytes: float
    latency_iqr_ns: float


@dataclass
class PerfEvaluation:
    trace_metrics: list[TracePerfMetrics] = field(default_factory=list)
    family_metrics: dict[str, dict] = field(default_factory=dict)
    aggregate: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_performance(
    engine_factory: EngineFactory,
    traces: list[WorkloadTrace],
    *,
    repetitions: int,
    warmup_prefix: int,
) -> PerfEvaluation:
    trace_metrics: list[TracePerfMetrics] = []
    for trace in traces:
        if warmup_prefix > 0:
            warm_trace = WorkloadTrace(
                trace_id=f"{trace.trace_id}_warmup",
                family=trace.family,
                seed=trace.seed,
                initial_items=trace.initial_items,
                operations=trace.operations[:warmup_prefix],
                hidden_params=trace.hidden_params,
            )
            run_trace(engine_factory, warm_trace, collect_timings=False)
        reps: list[RepetitionMetrics] = []
        for _ in range(repetitions):
            tracemalloc.start()
            result = run_trace(engine_factory, trace, collect_timings=True)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            latencies = result.op_latencies_ns or [0]
            elapsed = max(result.elapsed_seconds, 1e-12)
            reps.append(
                RepetitionMetrics(
                    elapsed_seconds=elapsed,
                    throughput_ops_per_sec=result.operation_count / elapsed,
                    p95_latency_ns=percentile(latencies, 95),
                    mean_latency_ns=statistics.fmean(latencies),
                    peak_memory_bytes=int(peak),
                )
            )
        trace_metrics.append(_aggregate_trace(trace, reps))
    return _aggregate_all(trace_metrics)


def percentile(values: list[int] | list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(float(v) for v in values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = rank - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _aggregate_trace(trace: WorkloadTrace, reps: list[RepetitionMetrics]) -> TracePerfMetrics:
    p95s = [rep.p95_latency_ns for rep in reps]
    q1 = percentile(p95s, 25)
    q3 = percentile(p95s, 75)
    return TracePerfMetrics(
        trace_id=trace.trace_id,
        family=trace.family,
        repetitions=reps,
        median_elapsed_seconds=statistics.median(rep.elapsed_seconds for rep in reps),
        median_throughput_ops_per_sec=statistics.median(rep.throughput_ops_per_sec for rep in reps),
        median_p95_latency_ns=statistics.median(p95s),
        median_peak_memory_bytes=statistics.median(rep.peak_memory_bytes for rep in reps),
        latency_iqr_ns=q3 - q1,
    )


def _aggregate_all(trace_metrics: list[TracePerfMetrics]) -> PerfEvaluation:
    family_metrics: dict[str, dict] = {}
    for metric in trace_metrics:
        rows = family_metrics.setdefault(metric.family, {"traces": []})
        rows["traces"].append(metric)
    for family, rows in family_metrics.items():
        traces = rows["traces"]
        rows["median_p95_latency_ns"] = statistics.median(t.median_p95_latency_ns for t in traces)
        rows["median_throughput_ops_per_sec"] = statistics.median(t.median_throughput_ops_per_sec for t in traces)
        rows["median_peak_memory_bytes"] = statistics.median(t.median_peak_memory_bytes for t in traces)
        rows["latency_iqr_ns"] = statistics.median(t.latency_iqr_ns for t in traces)
        rows["trace_count"] = len(traces)
        rows["traces"] = [asdict(t) for t in traces]
    aggregate = {
        "median_p95_latency_ns": statistics.median(t.median_p95_latency_ns for t in trace_metrics) if trace_metrics else None,
        "median_throughput_ops_per_sec": statistics.median(t.median_throughput_ops_per_sec for t in trace_metrics) if trace_metrics else None,
        "median_peak_memory_bytes": statistics.median(t.median_peak_memory_bytes for t in trace_metrics) if trace_metrics else None,
        "trace_count": len(trace_metrics),
    }
    return PerfEvaluation(trace_metrics=trace_metrics, family_metrics=family_metrics, aggregate=aggregate)

