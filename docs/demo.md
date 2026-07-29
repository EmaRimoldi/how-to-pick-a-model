# Demo

This is the shortest coherent path through AutoResearch Orchestration. The
benchmark is deliberately concrete: agents edit one CIFAR-10 training file,
`autoresearch/train.py`, then run evaluations and try to reduce validation loss.

The product question is:

> Should this task be run by one long-running agent, independent parallel
> agents, memory-augmented agents, a blackboard swarm, or a merge workflow?

The fastest way to inspect the artifact shape is the offline demo:

```bash
uv run agent-workflow demo
```

This command does not invoke Claude Code, GPUs, SLURM, or external model
providers. It writes deterministic fixture data under `runs/` so reviewers can
inspect the artifact shape before running live agents.

## 60-Second Script

AutoResearch Orchestration measures whether a more complex AI-agent workflow is
worth running.

The repo does three things:

1. Runs workflows through one CLI: `agent-workflow`.
2. Captures audit evidence: logs, snapshots, traces, shared-memory events, and
   certified hitting time.
3. Preserves experiments showing what was learned.

The strongest current result is the memory ablation experiment. Exploratory
search without memory, `T06`, was unstable: best `val_bpb = 0.933`, mean
`1.816`. The shared-memory version, `T07`, was better and much more stable:
best `0.914`, mean `1.049`, with Mann-Whitney `p < 0.001`.

The narrow takeaway is that more agent exploration is not automatically better.
Routing correction through memory can turn destructive exploration into
controlled exploration in this substrate.

## Generated Files

```text
runs/experiment_demo_.../
  config.json
  summary.json
  trajectories.csv
  workflow_card.md
  workflow_card.json
  report.md
  report.html
```

## What It Proves

The demo proves that the local CLI can generate a reviewable evidence bundle:

- one compact Workflow Card;
- one static HTML report;
- one machine-readable summary;
- one trajectory table shaped like live run output.

It does not prove that a live multi-agent workflow improved a real task. Use
`parallel`, `parallel-shared`, `swarm`, and `merge` modes for live evidence.

## Custom Output Directory

```bash
uv run agent-workflow demo --output-dir /tmp/agent-workflow-demo
```

Use `--experiment-id` for stable paths during screenshots or CI checks:

```bash
uv run agent-workflow demo \
  --output-dir /tmp/agent-workflow-demo \
  --experiment-id readme_demo
```

## Fast Reading Path

1. Read the selected benchmark baseline:
   `experiments/autoresearch-cifar10/starting-model-calibration/README.md`.

   The current baseline was chosen after 161 controlled non-agentic
   evaluations. The selected starting model is `width30_lr_low`, with
   `val_bpb = 0.841354` and future agent target `target_val_bpb = 0.824`.

2. Read the strongest agent-workflow finding:
   `experiments/autoresearch-cifar10/shared-memory-ablation/README.md`.

   | Trial | Meaning | Attempts | Best `val_bpb` | Mean `val_bpb` |
   |---|---|---:|---:|---:|
   | `T06` | exploratory search, no memory | 21 | 0.933 | 1.816 |
   | `T07` | exploratory search with shared memory | 41 | 0.914 | 1.049 |

3. Read why the evaluation protocol had to be calibrated:
   `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/README.md`.

## Technical Walkthrough

Show the benchmark task:

- `autoresearch/train.py`
- `autoresearch/prepare.py`
- `autoresearch/program.md`

Show the CLI surface:

```bash
uv run agent-workflow --help
uv run agent-workflow parallel --help
uv run agent-workflow parallel-shared --help
uv run agent-workflow swarm --help
uv run agent-workflow certified-time --help
uv run agent-workflow baseline-calibration --help
```

Show the evidence trail:

- `experiments/README.md`
- `experiments/autoresearch-cifar10/starting-model-calibration/README.md`
- `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/README.md`
- `experiments/autoresearch-cifar10/shared-memory-ablation/README.md`

Useful figures:

- `docs/assets/experiments/experiment-map.png`
- `experiments/autoresearch-cifar10/starting-model-calibration/results/figures/figure-04-recommended-baseline-detail.png`
- `experiments/autoresearch-cifar10/shared-memory-ablation/results/figures/figure-01-trial-outcomes.png`
- `experiments/autoresearch-cifar10/shared-memory-ablation/results/figures/figure-02-memory-stabilization.png`
- `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/results/figures/figure-01-fixed-time-compute-loss.png`
- `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/results/figures/figure-02-fixed-step-latency-cost.png`
- `experiments/autoresearch-cifar10/swarm-vs-independent-agents/results/figures/figure-01-validation-bpb-over-time.png`
- `experiments/autoresearch-cifar10/swarm-vs-independent-agents/results/figures/figure-04-swarm-memory-architecture.png`

The repo is explicit about limits: it shows a path toward rigorous workflow
evaluation on one controlled substrate, not a finished universal benchmark.
