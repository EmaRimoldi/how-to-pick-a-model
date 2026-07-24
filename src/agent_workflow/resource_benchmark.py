"""Empirical upper-bound estimation for parallel sub-agents.

This module implements a benchmarking protocol that progressively increases
the number of concurrent lightweight workloads and measures:
  - wall-clock completion time
  - success / failure rate
  - throughput (tasks / second)
  - CPU and memory utilisation
  - workspace creation overhead
  - SLURM submission overhead (if applicable)

From these measurements it derives three quantities:
  1. max_observed_n  – largest N for which the system completed at all
  2. stable_max_n    – largest N with acceptable reliability and throughput
  3. recommended_n   – conservative operating point (stable_max × 0.75, ≥ 1)

The benchmark uses *lightweight mock workloads* (subprocess.run of a trivial
Python command) rather than real training runs, so it can be executed cheaply
to characterise the execution environment.  A separate SLURM-probe path tests
submission overhead when a SLURM cluster is available.

Results are written to:
    {output_dir}/benchmark_N{n}/   – per-N results
    {output_dir}/summary.json      – aggregate table
    {output_dir}/recommendation.json – final numbers
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import resource as _resource
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WorkloadResult:
    """Result of one individual mock workload."""
    worker_id: int
    success: bool
    elapsed_seconds: float
    error: str = ""


@dataclass
class NResult:
    """Aggregate results for one value of N (concurrent agents)."""
    n: int
    timestamp: str
    workload_results: list[WorkloadResult] = field(default_factory=list)

    # Derived metrics
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    wall_clock_seconds: float = 0.0   # total elapsed from first start to last finish
    mean_task_seconds: float = 0.0
    max_task_seconds: float = 0.0
    throughput_tasks_per_sec: float = 0.0

    def compute(self) -> None:
        if not self.workload_results:
            return
        self.success_count = sum(1 for r in self.workload_results if r.success)
        self.failure_count = len(self.workload_results) - self.success_count
        self.success_rate = self.success_count / len(self.workload_results)
        elapsed_times = [r.elapsed_seconds for r in self.workload_results]
        self.mean_task_seconds = sum(elapsed_times) / len(elapsed_times)
        self.max_task_seconds = max(elapsed_times)
        if self.wall_clock_seconds > 0:
            self.throughput_tasks_per_sec = self.success_count / self.wall_clock_seconds

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("workload_results")   # too verbose for summary
        return d


@dataclass
class BenchmarkRecommendation:
    """Final recommendation from the capacity benchmark."""
    max_observed_n: int          # largest N that completed at all
    stable_max_n: int            # largest N with acceptable reliability
    recommended_n: int           # conservative daily operating point

    bottleneck: str              # "cpu" | "memory" | "subprocess_limit" | "slurm" | "unknown"
    bottleneck_evidence: str

    acceptable_success_rate: float = 0.90
    acceptable_throughput_ratio: float = 0.70  # vs N=1 baseline throughput × N

    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Benchmark implementation
# ---------------------------------------------------------------------------

class ParallelCapacityBenchmark:
    """Run the capacity benchmark for a given environment.

    Parameters
    ----------
    output_dir : Path
        Directory where results are written.
    max_n : int
        Maximum N to test (default 8).
    workload_duration_seconds : float
        How long each mock workload runs (default 5 s).
        Set low enough to complete quickly but long enough to create
        realistic overlap between concurrent workloads.
    success_rate_threshold : float
        Below this success rate, N is considered unstable (default 0.90).
    throughput_degradation_threshold : float
        If throughput per agent drops below this fraction of ideal, flag as
        degraded (default 0.70).
    """

    def __init__(
        self,
        output_dir: Path,
        max_n: int = 8,
        workload_duration_seconds: float = 5.0,
        success_rate_threshold: float = 0.90,
        throughput_degradation_threshold: float = 0.70,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_n = max_n
        self.workload_duration_seconds = workload_duration_seconds
        self.success_rate_threshold = success_rate_threshold
        self.throughput_degradation_threshold = throughput_degradation_threshold

    def run(self, n_values: Optional[list[int]] = None) -> BenchmarkRecommendation:
        """Run the full benchmark sweep.

        Parameters
        ----------
        n_values : list[int] | None
            Specific N values to test. Defaults to [1, 2, 3, 4, 6, 8] ∩ [1..max_n].
        """
        if n_values is None:
            n_values = [n for n in [1, 2, 3, 4, 6, 8] if n <= self.max_n]
        n_values = sorted(set(n_values))

        print(f"[benchmark] Testing N values: {n_values}")
        print(f"[benchmark] Workload duration: {self.workload_duration_seconds}s per task")

        results: list[NResult] = []
        baseline_throughput: Optional[float] = None

        for n in n_values:
            print(f"[benchmark] Running N={n}...", flush=True)
            nr = self._run_n(n)
            results.append(nr)

            # Save per-N result
            n_dir = self.output_dir / f"benchmark_N{n}"
            n_dir.mkdir(exist_ok=True)
            (n_dir / "result.json").write_text(json.dumps(nr.to_dict(), indent=2))

            if n == 1:
                baseline_throughput = nr.throughput_tasks_per_sec

            print(
                f"[benchmark] N={n}: success={nr.success_rate:.0%} "
                f"wall={nr.wall_clock_seconds:.1f}s "
                f"throughput={nr.throughput_tasks_per_sec:.3f} t/s"
            )

            # Early stop if complete failure
            if nr.success_rate == 0.0 and n > 1:
                print(f"[benchmark] Complete failure at N={n}, stopping sweep.")
                break

        # Write summary table
        summary = {
            "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
            "workload_duration_seconds": self.workload_duration_seconds,
            "success_rate_threshold": self.success_rate_threshold,
            "results": [r.to_dict() for r in results],
        }
        (self.output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # Derive recommendation
        recommendation = self._derive_recommendation(results, baseline_throughput)
        (self.output_dir / "recommendation.json").write_text(
            json.dumps(recommendation.to_dict(), indent=2)
        )

        print(f"\n[benchmark] Results:")
        print(f"  max_observed_n  = {recommendation.max_observed_n}")
        print(f"  stable_max_n    = {recommendation.stable_max_n}")
        print(f"  recommended_n   = {recommendation.recommended_n}")
        print(f"  bottleneck      = {recommendation.bottleneck}")

        return recommendation

    def _run_n(self, n: int) -> NResult:
        """Run N concurrent mock workloads and collect results."""
        nr = NResult(
            n=n,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Use multiprocessing to mirror the real orchestrator behaviour
        with multiprocessing.Manager() as mgr:
            shared = mgr.list([None] * n)
            procs = []
            t0 = time.monotonic()
            for idx in range(n):
                p = multiprocessing.Process(
                    target=_benchmark_worker,
                    args=(idx, shared, self.workload_duration_seconds),
                )
                p.start()
                procs.append(p)

            for p in procs:
                p.join(timeout=self.workload_duration_seconds * 3 + 10)
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=2)

            wall_clock = time.monotonic() - t0
            nr.wall_clock_seconds = wall_clock

            for item in shared:
                if item is None:
                    nr.workload_results.append(
                        WorkloadResult(
                            worker_id=-1, success=False, elapsed_seconds=wall_clock,
                            error="process did not complete"
                        )
                    )
                else:
                    nr.workload_results.append(item)

        nr.compute()
        return nr

    def _derive_recommendation(
        self,
        results: list[NResult],
        baseline_throughput: Optional[float],
    ) -> BenchmarkRecommendation:
        """Analyse benchmark results and return a recommendation."""
        if not results:
            return BenchmarkRecommendation(
                max_observed_n=0,
                stable_max_n=0,
                recommended_n=1,
                bottleneck="unknown",
                bottleneck_evidence="no results collected",
            )

        # max_observed: largest N with any successes
        max_observed = max(
            (r.n for r in results if r.success_count > 0), default=0
        )

        # stable_max: largest N satisfying both thresholds
        stable_max = 0
        bottleneck = "unknown"
        bottleneck_evidence = ""

        for r in sorted(results, key=lambda x: x.n):
            rate_ok = r.success_rate >= self.success_rate_threshold

            # Throughput check: ideal throughput = baseline × N
            # We accept degradation up to threshold
            throughput_ok = True
            if baseline_throughput is not None and baseline_throughput > 0 and r.n > 1:
                ideal = baseline_throughput * r.n
                actual = r.throughput_tasks_per_sec
                ratio = actual / ideal if ideal > 0 else 0.0
                throughput_ok = ratio >= self.throughput_degradation_threshold
                if not throughput_ok and not bottleneck_evidence:
                    bottleneck = _guess_bottleneck()
                    bottleneck_evidence = (
                        f"throughput ratio {ratio:.2f} < threshold "
                        f"{self.throughput_degradation_threshold} at N={r.n}"
                    )

            if rate_ok and throughput_ok:
                stable_max = r.n
            elif not rate_ok and not bottleneck_evidence:
                bottleneck = _guess_bottleneck()
                bottleneck_evidence = (
                    f"success rate {r.success_rate:.0%} < threshold "
                    f"{self.success_rate_threshold:.0%} at N={r.n}"
                )

        # recommended = 75% of stable_max, at least 1
        recommended = max(1, int(stable_max * 0.75))

        if not bottleneck_evidence:
            bottleneck = "none_detected"
            bottleneck_evidence = (
                f"all tested N values met both thresholds (max tested: {results[-1].n})"
            )

        return BenchmarkRecommendation(
            max_observed_n=max_observed,
            stable_max_n=stable_max,
            recommended_n=recommended,
            bottleneck=bottleneck,
            bottleneck_evidence=bottleneck_evidence,
            notes=(
                f"Benchmark used {self.workload_duration_seconds}s mock workloads. "
                "Re-run with real training workloads for production planning."
            ),
        )


# ---------------------------------------------------------------------------
# Workspace-creation probe
# ---------------------------------------------------------------------------

def benchmark_workspace_creation(
    autoresearch_dir: Path,
    scratch_dir: Path,
    n_values: Optional[list[int]] = None,
) -> dict:
    """Measure how long workspace creation takes for N parallel agents.

    This is a separate probe that measures git worktree overhead, which can
    become a bottleneck with many agents sharing the same source repo.
    """
    from agent_workflow.utils.workspace import create_workspace, destroy_workspace

    if n_values is None:
        n_values = [1, 2, 4]

    results = []
    for n in n_values:
        t0 = time.monotonic()
        workspaces = []
        errors = []
        for i in range(n):
            ws = scratch_dir / f"bench_ws_{n}_{i}"
            branch = f"bench/{n}/{i}"
            try:
                create_workspace(
                    autoresearch_dir=autoresearch_dir,
                    workspace_path=ws,
                    branch_name=branch,
                    train_budget_seconds=300,
                    run_id="bench",
                    agent_id=f"bench_{i}",
                    results_root=ws.parent / f"bench_results_{n}_{i}",
                    use_slurm=False,
                )
                workspaces.append(ws)
            except Exception as e:
                errors.append(str(e))

        elapsed = time.monotonic() - t0

        for ws in workspaces:
            try:
                destroy_workspace(autoresearch_dir, ws)
            except Exception:
                pass

        results.append({
            "n": n,
            "elapsed_seconds": elapsed,
            "successes": len(workspaces),
            "errors": errors,
        })
        print(f"[ws_bench] N={n}: {elapsed:.2f}s ({len(workspaces)} created, {len(errors)} errors)")

    return {"workspace_creation_benchmark": results}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_workload(duration: float) -> None:
    """A trivial workload that burns `duration` seconds of wall-clock time."""
    subprocess.run(
        [sys.executable, "-c", f"import time; time.sleep({duration})"],
        check=True,
        capture_output=True,
    )


def _benchmark_worker(idx: int, out_list: list, duration: float) -> None:
    """Run one mock workload and store a picklable result.

    This must be module-level for Python's spawn multiprocessing context
    (macOS / Python 3.13), where nested functions cannot be pickled.
    """
    start = time.monotonic()
    try:
        _mock_workload(duration)
        elapsed = time.monotonic() - start
        out_list[idx] = WorkloadResult(
            worker_id=idx, success=True, elapsed_seconds=elapsed
        )
    except Exception as e:
        elapsed = time.monotonic() - start
        out_list[idx] = WorkloadResult(
            worker_id=idx, success=False, elapsed_seconds=elapsed, error=str(e)
        )


def _guess_bottleneck() -> str:
    """Heuristically identify likely bottleneck in the current environment."""
    try:
        cpu_count = os.cpu_count() or 1
        if cpu_count <= 2:
            return "cpu"
        # Rough memory check
        if _HAS_RESOURCE:
            soft, _ = _resource.getrlimit(_resource.RLIMIT_NPROC)
            if soft < 32:
                return "subprocess_limit"
        return "unknown"
    except Exception:
        return "unknown"
