# Demo Script

This is the shortest coherent demo of AutoResearch Orchestration.

## 60-Second Demo

AutoResearch Orchestration measures whether a more complex AI-agent workflow is worth running.

The benchmark is deliberately concrete: agents edit one CIFAR-10 training file,
`autoresearch/train.py`, then run evaluations and try to reduce `val_bpb`
validation loss.

The product question is:

> Should this task be run by one long-running agent, independent parallel
> agents, memory-augmented agents, a blackboard swarm, or a merge workflow?

The repo does three things:

1. Runs the workflows through one CLI: `agent-workflow`.
2. Captures audit evidence: logs, snapshots, traces, shared-memory events, and
   certified hitting time.
3. Preserves the experiments showing what was learned.

The strongest current result is the memory ablation experiment. Exploratory search
without memory, `T06`, was unstable: best `val_bpb = 0.933`, mean
`1.816`. The shared-memory version, `T07`, was better and much more stable:
best `0.914`, mean `1.049`, with Mann-Whitney `p < 0.001`.

The takeaway is narrow but useful: more agent exploration is not automatically
better. Routing correction through memory can turn destructive exploration into
controlled exploration.

## 5-Minute Technical Walkthrough

### 1. Show the benchmark task

Files:

- `autoresearch/train.py`
- `autoresearch/prepare.py`
- `autoresearch/program.md`

What to say:

The substrate is intentionally small and inspectable. Agents are allowed to edit
`train.py`; evaluation reports `val_bpb`; fixed-step runs make comparisons less
dependent on machine load.

### 2. Show the CLI surface

```bash
uv run agent-workflow --help
uv run agent-workflow parallel --help
uv run agent-workflow parallel-shared --help
uv run agent-workflow swarm --help
uv run agent-workflow certified-time --help
uv run agent-workflow baseline-calibration --help
```

What to say:

The public surface is one CLI, not a pile of ad hoc scripts. Historical scripts
are still present for deeper inspection, but the canonical route is
`agent-workflow`.

### 3. Show the evidence trail

Files:

- `experiments/README.md`
- `experiments/autoresearch/01_baseline/README.md`
- `experiments/autoresearch/02_evaluation_protocol_calibration/README.md`
- `experiments/autoresearch/03_agent_memory_ablation/README.md`

What to say:

The repo is structured as a sequence of experiments. Each experiment has a
question, what was run, the result, the caveat, and the first file to read.

### 4. Show the strongest empirical result

File:

- `experiments/autoresearch/03_agent_memory_ablation/README.md`

Key numbers:

| Trial | Meaning | Attempts | Best `val_bpb` | Mean `val_bpb` |
|---|---|---:|---:|---:|
| `T06` | exploratory search, no memory | 21 | 0.933 | 1.816 |
| `T07` | exploratory search with shared memory | 41 | 0.914 | 1.049 |

What to say:

This is not a general claim that memory always helps. It is evidence that
unguided exploration can become destructive, and that shared memory can reduce
catastrophic repeats in this setting.

### 5. Show what is not claimed

Files:

- `docs/reviewer_checklist.md`
- `experiments/catalog.md`

What to say:

The repo is explicit about limits. The experiments show a path toward rigorous
AutoResearch Orchestration evaluation on one controlled substrate, not a finished universal
benchmark.

## Local Smoke Demo

This demo does not require Claude Code:

```bash
uv sync --dev --frozen
uv run pytest tests -q
uv run agent-workflow --help
```

To run agent experiments, follow `docs/reproducibility.md` because those runs
require Claude Code authentication and a clean workspace.
