#!/usr/bin/env python3
"""CLI: run the parallel-capacity benchmark.

Measures the empirical upper bound on the number of sub-agents that can run
concurrently in this environment.

Usage:
    python scripts/benchmark_parallel_capacity.py
    python scripts/benchmark_parallel_capacity.py --max-n 6 --duration 3.0
    python scripts/benchmark_parallel_capacity.py --output-dir runs/bench_capacity
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from agent_workflow.resource_benchmark import ParallelCapacityBenchmark


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the maximum number of parallel sub-agents."
    )
    parser.add_argument(
        "--max-n", type=int, default=8,
        help="Maximum number of concurrent agents to test (default: 8).",
    )
    parser.add_argument(
        "--duration", type=float, default=5.0,
        help="Seconds each mock workload runs (default: 5.0).",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Where to write benchmark results (default: runs/bench_capacity_<timestamp>).",
    )
    parser.add_argument(
        "--n-values", type=str, default=None,
        help="Comma-separated N values to test, e.g. '1,2,4,8'. "
             "Overrides --max-n sweep.",
    )
    parser.add_argument(
        "--success-threshold", type=float, default=0.90,
        help="Minimum acceptable success rate (default: 0.90).",
    )
    parser.add_argument(
        "--throughput-threshold", type=float, default=0.70,
        help="Minimum acceptable throughput ratio vs ideal (default: 0.70).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).parents[1]
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = repo_root / "runs" / f"bench_capacity_{ts}"

    n_values = None
    if args.n_values:
        n_values = [int(x.strip()) for x in args.n_values.split(",")]

    print(f"[benchmark] Output directory: {output_dir}")

    bench = ParallelCapacityBenchmark(
        output_dir=output_dir,
        max_n=args.max_n,
        workload_duration_seconds=args.duration,
        success_rate_threshold=args.success_threshold,
        throughput_degradation_threshold=args.throughput_threshold,
    )
    recommendation = bench.run(n_values=n_values)

    print("\n=== Capacity Benchmark Results ===")
    print(f"  max_observed_n  : {recommendation.max_observed_n}")
    print(f"  stable_max_n    : {recommendation.stable_max_n}")
    print(f"  recommended_n   : {recommendation.recommended_n}")
    print(f"  bottleneck      : {recommendation.bottleneck}")
    print(f"  evidence        : {recommendation.bottleneck_evidence}")
    print(f"\nFull results in: {output_dir}")


if __name__ == "__main__":
    main()
