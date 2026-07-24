# Parallel Capacity: Finding the Empirical Upper Bound on Sub-Agents

## Overview

The number of Claude Code sub-agents that can run concurrently is constrained by
multiple environmental factors. Rather than guessing a limit, the system provides a
benchmark that measures these constraints empirically and derives a principled
recommendation.

## The Three Key Quantities

| Quantity | Definition | How Derived |
|---|---|---|
| `max_observed_n` | Largest N for which all workloads complete | Any successes at that N |
| `stable_max_n` | Largest N meeting both acceptability thresholds | success_rate ≥ 0.90 AND throughput_ratio ≥ 0.70 |
| `recommended_n` | Conservative daily operating point | `floor(stable_max_n × 0.75)`, minimum 1 |

## How to Run the Benchmark

```bash
python scripts/benchmark_parallel_capacity.py
```

With custom parameters:
```bash
python scripts/benchmark_parallel_capacity.py \
    --max-n 8 \
    --duration 5.0 \
    --output-dir runs/capacity_bench \
    --success-threshold 0.90 \
    --throughput-threshold 0.70
```

Or specific N values:
```bash
python scripts/benchmark_parallel_capacity.py --n-values 1,2,4,6,8
```

Results are written to:
```
runs/bench_capacity_<timestamp>/
    benchmark_N1/result.json
    benchmark_N2/result.json
    ...
    summary.json         # table of all N results
    recommendation.json  # the three key quantities + bottleneck analysis
```

## Bottleneck Analysis

The benchmark identifies which resource is the constraint:

- **subprocess_limit** — OS limit on number of concurrent processes
- **cpu** — fewer than 4 logical CPUs available
- **memory** — system memory pressure under concurrent load
- **slurm** — SLURM queue slots exhausted (detected by job submission failures)
- **unknown** — no specific bottleneck detected at tested scale
- **none_detected** — all tested N values passed both thresholds

## Acceptability Criteria

**Success rate** threshold (default 0.90):
- At least 90% of concurrent workloads must complete without error
- Below this: some agents are crashing or timing out at that parallelism level

**Throughput ratio** threshold (default 0.70):
- `actual_throughput / (N × baseline_throughput_at_N=1) ≥ 0.70`
- Below this: significant interference between concurrent workloads
- I.e., adding more agents yields less than 70% of the ideal scaling

## Known Environmental Constraints for This System

Based on the autoresearch experiment setup:

1. **GPU slots** — Each agent submits one SLURM job requiring `gpu:1`. The number of
   available GPU slots in the `pi_tpoggio` partition is the hard upper bound for
   simultaneous training jobs. Check available GPUs with `sinfo -p pi_tpoggio`.

2. **Git worktrees** — Each agent uses a separate git worktree branched from
   `autoresearch/`. Worktree creation is sequential and takes ~1-3s per workspace.
   With many agents, workspace setup can take tens of seconds.

3. **SLURM queue limits** — The partition may impose per-user job limits. Check with
   `scontrol show partition pi_tpoggio`.

4. **Claude API rate limits** — Each sub-agent calls the Claude API independently.
   Concurrent API calls from many agents may hit per-minute token limits.

5. **Process count** — Each agent runs as a separate `multiprocessing.Process`. The
   OS limit (typically 4096 user processes) is rarely the bottleneck.

## Recommended Workflow

1. Run the benchmark once for your target cluster:
   ```bash
   python scripts/benchmark_parallel_capacity.py --max-n 8
   ```

2. Check GPU availability:
   ```bash
   sinfo -p pi_tpoggio -o "%n %G %C"
   ```

3. Use `recommended_n` from the benchmark output as the default `--n-agents` in
   your parallel experiments.

4. Re-run the benchmark when the cluster configuration changes significantly.

## Benchmark Limitations

The default benchmark uses **lightweight mock workloads** (Python sleep loops), not
real training jobs. This measures process scheduling and OS-level overhead accurately
but does not capture:

- SLURM queue competition from other users
- GPU memory pressure with concurrent training jobs
- NFS/storage I/O contention from concurrent `uv run train.py`
- Claude API rate limiting under concurrent requests

For a production capacity estimate, run the benchmark with `--duration` set to a
realistic training time (e.g., 300s) and monitor SLURM queue behavior manually.
