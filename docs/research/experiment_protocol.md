# Experiment Protocol

This protocol describes how to run a matched AutoResearch Orchestration experiment using the
canonical `agent-workflow` CLI. For machine setup and Claude Code authentication, read
[`../reproducibility.md`](../reproducibility.md) first.

## Core Question

A matched experiment compares agent workflow modes on the same AutoResearch
task:

- `single-long`: one agent with a longer budget.
- `parallel`: multiple independent agents.
- `parallel-shared`: multiple agents with a shared result log.
- `swarm`: blackboard-style coordination.
- `merge`: post-hoc merge of candidates.

The measured outcome is whether the workflow reaches a target `val_bpb` faster,
cheaper, or more reliably than the baseline.

## Preflight

Run local checks:

```bash
uv sync --dev --frozen
uv run pytest tests -q
uv run agent-workflow --help
```

Prepare data:

```bash
cd autoresearch
uv run python prepare.py
cd ..
```

Verify Claude Code:

```bash
claude --version
claude doctor
claude auth status
```

## Benchmark Baseline

The current calibrated baseline comes from
[`../../experiments/autoresearch/01_baseline/README.md`](../../experiments/autoresearch/01_baseline/README.md):

```text
starting_model = width 30, lower learning rate
internal_id = width30_lr_low
starting val_bpb = 0.841354
target_val_bpb = 0.824
fixed-length evaluator = AUTOSEARCH_MAX_STEPS=1170
```

Use this baseline for new reviewer-grade comparisons unless a newer calibration
experiment supersedes it.

## Matched Run Pattern

Use the same config, model, evaluator, target threshold, and wall-clock budget
across modes.

### Single long

```bash
uv run agent-workflow single-long \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --target-val-bpb 0.824 \
  --success-confidence 0.80 \
  --experiment-id study06_single_long
```

### Independent parallel

```bash
uv run agent-workflow parallel \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --target-val-bpb 0.824 \
  --success-confidence 0.80 \
  --experiment-id study06_parallel
```

### Shared-memory parallel

```bash
uv run agent-workflow parallel-shared \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --target-val-bpb 0.824 \
  --success-confidence 0.80 \
  --experiment-id study06_parallel_shared
```

### Swarm

```bash
uv run agent-workflow swarm \
  --run \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --n-agents 2 \
  --experiment-id study06_swarm
```

The current swarm surface delegates to the integrated swarm runtime. Its
blackboard can also be initialized independently:

```bash
uv run agent-workflow swarm --blackboard-dir runs/study06_swarm_blackboard
```

## Output Structure

Agent runs write under `runs/` by default. The exact tree varies by mode, but a
reviewable run should preserve:

```text
runs/
  experiment_<id>/
    config.json
    mode_<mode>/
      agent_0/
        workspace/
        logs/
        results/
          trajectory.jsonl
          results.tsv
          training_runs.jsonl
          metadata.json
          snapshots/
      aggregate/
        combined_summary.json
        comparison_table.csv
        experiment_report.txt
```

## Analysis Workflow

After runs finish:

1. Check that each agent has `results.tsv`, `trajectory.jsonl`, and logs.
2. Recompute certified hitting-time if a target threshold was pre-registered:

   ```bash
   uv run agent-workflow certified-time runs/experiment_<id> \
     --target-val-bpb 0.824 \
     --confidence 0.80
   ```

3. Compare modes only when evaluator settings, model, and target threshold match.
4. Move final summaries, tables, and figures into a named `experiments/<experiment>/`
   folder. Do not commit raw transient workspaces unless they are needed for
   reproducibility.

## Caveats

- Historical summaries are not guaranteed to be exactly reproducible because the
  Claude Code binary, model snapshots, and service behavior may change.
- `--serialized-evaluator` is recommended on shared machines to avoid
  contention masquerading as a workflow effect.
- A single replicate is a probe, not a confirmatory result.
- Swarm historical baselines in `experiments/autoresearch/04_swarm_baselines/` are context only;
  they are not normalized rows for the current BP 2x2 decomposition.
