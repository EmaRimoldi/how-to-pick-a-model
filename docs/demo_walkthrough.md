# Demo Walkthrough

This repository is easiest to read as an evidence trail, not as a UI demo.
The concrete task is AutoResearch: agents edit one CIFAR-10 training script,
run evaluations, and try to reduce validation loss.

## The Task

`autoresearch/` is the benchmark substrate used by the runtime:

- `autoresearch/train.py` is the file agents are allowed to edit.
- `autoresearch/prepare.py` owns data loading and evaluation.
- `val_bpb` is the reported validation-loss proxy; lower is better.
- Agent modes differ only in how search is coordinated: single long run,
  parallel independent runs, private/shared memory, swarm blackboard, or merge.

This gives the repo a concrete experimental question:

> Which agent workflow finds better `train.py` edits per unit of wall time,
> cost, and coordination overhead?

## Fastest Reading Path

1. Read the selected benchmark baseline:
   [`experiments/autoresearch/01_baseline/README.md`](../experiments/autoresearch/01_baseline/README.md).

   The current baseline was chosen after 161 controlled non-agentic evaluations.
   The selected starting model is "width 30, lower learning rate" (internal ID
   `width30_lr_low`), with `val_bpb = 0.841354` and future agent target
   `target_val_bpb = 0.824`.

2. Read the strongest agent-workflow finding:
   [`experiments/autoresearch/03_agent_memory_ablation/README.md`](../experiments/autoresearch/03_agent_memory_ablation/README.md).

   The most informative comparison is `T06` vs `T07`:

   | Trial | Meaning | Attempts | Best `val_bpb` | Mean `val_bpb` |
   |---|---|---:|---:|---:|
   | `T06` | exploratory search, no memory | 21 | 0.933 | 1.816 |
   | `T07` | exploratory search with shared memory | 41 | 0.914 | 1.049 |

   The interpretation is that exploration without routing correction behaves
   like a random walk, while shared memory reduces catastrophic repeats.

3. Read why the evaluation protocol had to be calibrated:
   [`experiments/autoresearch/02_evaluation_protocol_calibration/README.md`](../experiments/autoresearch/02_evaluation_protocol_calibration/README.md).

   This experiment combines the two protocol checks that make later comparisons
   interpretable: repeated baseline runs must match exactly, and training should
   be fixed-step rather than fixed-time so hardware contention appears as
   latency instead of lower model quality.

## What To Look At Visually

The most useful result figures are:

- [`docs/assets/experiments/experiment-map.png`](../docs/assets/experiments/experiment-map.png)
- [`experiments/autoresearch/01_baseline/results/figures/figure-04-recommended-baseline-detail.png`](../experiments/autoresearch/01_baseline/results/figures/figure-04-recommended-baseline-detail.png)
- [`experiments/autoresearch/03_agent_memory_ablation/results/figures/figure-01-trial-outcomes.png`](../experiments/autoresearch/03_agent_memory_ablation/results/figures/figure-01-trial-outcomes.png)
- [`experiments/autoresearch/03_agent_memory_ablation/results/figures/figure-02-memory-stabilization.png`](../experiments/autoresearch/03_agent_memory_ablation/results/figures/figure-02-memory-stabilization.png)
- [`experiments/autoresearch/02_evaluation_protocol_calibration/results/figures/figure-01-fixed-time-compute-loss.png`](../experiments/autoresearch/02_evaluation_protocol_calibration/results/figures/figure-01-fixed-time-compute-loss.png)
- [`experiments/autoresearch/02_evaluation_protocol_calibration/results/figures/figure-02-fixed-step-latency-cost.png`](../experiments/autoresearch/02_evaluation_protocol_calibration/results/figures/figure-02-fixed-step-latency-cost.png)
- [`experiments/autoresearch/04_swarm_baselines/results/figures/figure-01-validation-bpb-over-time.png`](../experiments/autoresearch/04_swarm_baselines/results/figures/figure-01-validation-bpb-over-time.png)
- [`experiments/autoresearch/04_swarm_baselines/results/figures/figure-04-swarm-memory-architecture.png`](../experiments/autoresearch/04_swarm_baselines/results/figures/figure-04-swarm-memory-architecture.png)

## Runnable Surface

The current public CLI is:

```bash
uv run agent-workflow --help
uv run agent-workflow parallel --help
uv run agent-workflow parallel-shared --help
uv run agent-workflow single-long --help
uv run agent-workflow single-memory --help
uv run agent-workflow swarm --help
uv run agent-workflow merge --help
uv run agent-workflow certified-time --help
uv run agent-workflow baseline-calibration --help
```

The repository does not include raw private run logs or local datasets. Curated
summaries and figures are checked in under `experiments/`; new full runs write to
`runs/`.
