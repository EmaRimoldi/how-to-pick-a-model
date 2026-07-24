"""Tests for resource_benchmark.py — capacity benchmark logic."""
import json
from pathlib import Path

import pytest

from agent_workflow.resource_benchmark import (
    BenchmarkRecommendation,
    NResult,
    ParallelCapacityBenchmark,
    WorkloadResult,
)


@pytest.fixture
def bench(tmp_path):
    return ParallelCapacityBenchmark(
        output_dir=tmp_path / "bench",
        max_n=4,
        workload_duration_seconds=0.2,   # very short for tests
        success_rate_threshold=0.90,
        throughput_degradation_threshold=0.50,
    )


class TestNResultCompute:
    def test_all_success(self):
        nr = NResult(n=2, timestamp="T")
        nr.workload_results = [
            WorkloadResult(0, True, 1.0),
            WorkloadResult(1, True, 1.2),
        ]
        nr.wall_clock_seconds = 1.2
        nr.compute()
        assert nr.success_count == 2
        assert nr.failure_count == 0
        assert nr.success_rate == pytest.approx(1.0)
        assert nr.throughput_tasks_per_sec == pytest.approx(2 / 1.2)

    def test_partial_failure(self):
        nr = NResult(n=3, timestamp="T")
        nr.workload_results = [
            WorkloadResult(0, True, 1.0),
            WorkloadResult(1, False, 1.1, error="crash"),
            WorkloadResult(2, True, 0.9),
        ]
        nr.wall_clock_seconds = 1.1
        nr.compute()
        assert nr.success_count == 2
        assert nr.failure_count == 1
        assert nr.success_rate == pytest.approx(2 / 3)

    def test_to_dict_excludes_workload_results(self):
        nr = NResult(n=1, timestamp="T")
        nr.workload_results = [WorkloadResult(0, True, 1.0)]
        nr.compute()
        d = nr.to_dict()
        assert "workload_results" not in d


class TestDeriveRecommendation:
    def _make_results(self, ns, success_rates, wall_times) -> list[NResult]:
        results = []
        for n, rate, wall in zip(ns, success_rates, wall_times):
            nr = NResult(n=n, timestamp="T")
            nr.success_count = int(n * rate)
            nr.failure_count = n - nr.success_count
            nr.success_rate = rate
            nr.wall_clock_seconds = wall
            nr.throughput_tasks_per_sec = nr.success_count / wall if wall > 0 else 0
            results.append(nr)
        return results

    def test_all_pass_recommends_largest(self):
        bench = ParallelCapacityBenchmark(
            Path("/tmp"), max_n=4,
            success_rate_threshold=0.90,
            throughput_degradation_threshold=0.50,
        )
        results = self._make_results(
            ns=[1, 2, 4],
            success_rates=[1.0, 1.0, 1.0],
            wall_times=[1.0, 1.0, 1.0],
        )
        baseline_tp = results[0].throughput_tasks_per_sec
        rec = bench._derive_recommendation(results, baseline_tp)
        assert rec.stable_max_n == 4

    def test_failure_caps_stable_max(self):
        bench = ParallelCapacityBenchmark(
            Path("/tmp"), max_n=4,
            success_rate_threshold=0.90,
            throughput_degradation_threshold=0.50,
        )
        # N=4 fails with only 50% success rate
        results = self._make_results(
            ns=[1, 2, 4],
            success_rates=[1.0, 1.0, 0.5],
            wall_times=[1.0, 1.0, 1.0],
        )
        baseline_tp = results[0].throughput_tasks_per_sec
        rec = bench._derive_recommendation(results, baseline_tp)
        assert rec.stable_max_n == 2

    def test_recommended_is_75_percent_of_stable(self):
        bench = ParallelCapacityBenchmark(
            Path("/tmp"), max_n=8,
            success_rate_threshold=0.90,
            throughput_degradation_threshold=0.50,
        )
        results = self._make_results(
            ns=[1, 2, 4, 8],
            success_rates=[1.0, 1.0, 1.0, 1.0],
            wall_times=[1.0, 1.0, 1.0, 1.0],
        )
        baseline_tp = results[0].throughput_tasks_per_sec
        rec = bench._derive_recommendation(results, baseline_tp)
        assert rec.recommended_n == max(1, int(rec.stable_max_n * 0.75))

    def test_recommended_at_least_1(self):
        bench = ParallelCapacityBenchmark(
            Path("/tmp"), max_n=2,
            success_rate_threshold=0.90,
            throughput_degradation_threshold=0.50,
        )
        # All fail
        results = self._make_results([1], [0.0], [1.0])
        rec = bench._derive_recommendation(results, 0.0)
        assert rec.recommended_n >= 1

    def test_empty_results_returns_safe_default(self):
        bench = ParallelCapacityBenchmark(Path("/tmp"), max_n=4)
        rec = bench._derive_recommendation([], None)
        assert rec.recommended_n >= 1


class TestBenchmarkRun:
    def test_run_produces_summary_json(self, bench, tmp_path):
        bench.run(n_values=[1, 2])
        assert (bench.output_dir / "summary.json").exists()

    def test_run_produces_recommendation_json(self, bench):
        bench.run(n_values=[1, 2])
        assert (bench.output_dir / "recommendation.json").exists()

    def test_run_produces_per_n_results(self, bench):
        bench.run(n_values=[1, 2])
        assert (bench.output_dir / "benchmark_N1" / "result.json").exists()
        assert (bench.output_dir / "benchmark_N2" / "result.json").exists()

    def test_recommendation_fields_present(self, bench):
        rec = bench.run(n_values=[1])
        assert isinstance(rec.max_observed_n, int)
        assert isinstance(rec.stable_max_n, int)
        assert isinstance(rec.recommended_n, int)
        assert rec.recommended_n >= 1

    def test_run_n1_always_succeeds(self, bench):
        bench.run(n_values=[1])
        rec_path = bench.output_dir / "recommendation.json"
        rec = json.loads(rec_path.read_text())
        assert rec["max_observed_n"] >= 1
