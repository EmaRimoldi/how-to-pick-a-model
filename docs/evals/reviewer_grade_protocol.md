# Reviewer-Grade BP Protocol

This protocol is the confirmatory version of the AutoResearch BP experiment. It
addresses the main construct-validity weaknesses from the exploratory experiments.

## Estimand

Pre-register:

- `q*`: target latent-loss threshold, implemented as `--target-val-bpb`.
- `1 - delta`: certified success confidence, implemented as `--success-confidence`.
- evaluator stopping rule: fixed-step, implemented as `--train-max-steps`.
- evaluator concurrency: serialized, implemented as `--serialized-evaluator`.

The analysis estimates:

```text
T_wall(q*, delta) = earliest critical-path wall time by which at least
ceil((1 - delta) * N) independent replicates hit q*

T_cost(q*, delta) = analogous empirical quantile on cumulative cost proxy
```

The critical path includes LLM turns, file writes, and training evaluations. The
logs also separate `agent_deliberation_wall_seconds` from
`evaluator_wall_seconds` so ablations can report LLM-only timing without
renaming it `T_wall`.

## Required Controls

Use fixed-step evaluation for quality:

```bash
--train-max-steps 1170
```

This makes each `train.py` complete the same number of gradient updates. The
`--train-budget` argument remains a timeout guard, not the quality-defining
budget.

Use a serialized evaluator for parallel agents:

```bash
--serialized-evaluator
```

This lets agents deliberate in parallel but forces `train.py` evaluations through
one shared lock. That prevents CPU/GPU contention from changing validation loss.
Any remaining parallelism effect is due to agentic search behavior, not to one
training process starving another.

Use true replicates:

```text
rg_d00_rep01 ... rg_d00_rep05
rg_d10_rep01 ... rg_d10_rep05
rg_d01_rep01 ... rg_d01_rep05
rg_d11_rep01 ... rg_d11_rep05
```

Do not treat the training runs inside one agent trajectory as independent
replicates for configuration-level p-values.

## Example Commands

Single/no-memory (`d00`):

```bash
uv run agent-workflow single-long \
  --experiment-id rg_d00_rep01 \
  --time-budget 90 \
  --train-budget 300 \
  --train-max-steps 1170 \
  --target-val-bpb 0.90 \
  --success-confidence 0.80 \
  --serialized-evaluator
```

Single/memory (`d10`):

```bash
uv run agent-workflow single-memory \
  --experiment-id rg_d10_rep01 \
  --time-budget 90 \
  --train-budget 300 \
  --train-max-steps 1170 \
  --target-val-bpb 0.90 \
  --success-confidence 0.80 \
  --serialized-evaluator
```

Parallel/no-memory (`d01`):

```bash
uv run agent-workflow parallel \
  --experiment-id rg_d01_rep01 \
  --time-budget 90 \
  --train-budget 300 \
  --train-max-steps 1170 \
  --target-val-bpb 0.90 \
  --success-confidence 0.80 \
  --serialized-evaluator
```

Parallel/shared-memory (`d11`):

```bash
uv run agent-workflow parallel-shared \
  --experiment-id rg_d11_rep01 \
  --time-budget 90 \
  --train-budget 300 \
  --train-max-steps 1170 \
  --target-val-bpb 0.90 \
  --success-confidence 0.80 \
  --serialized-evaluator
```

Repeat each command with `rep02` through `rep05` before making confirmatory
claims.

A YAML starting point is available at
[`reviewer_grade_fixed_step_config.yaml`](reviewer_grade_fixed_step_config.yaml).

## Certified-Time Analysis

Run:

```bash
uv run agent-workflow certified-time \
  --target-val-bpb 0.90 \
  --confidence 0.80 \
  --require-reevaluation \
  --min-evaluations 2 \
  --out results/reviewer_grade/certified_time.json \
  runs/experiment_rg_d00_* \
  runs/experiment_rg_d10_* \
  runs/experiment_rg_d01_* \
  runs/experiment_rg_d11_*
```

Outputs:

- `certified_time.json`: machine-readable estimates and replicate-level hits.
- `certified_time.md`: reviewer-facing table of `T_wall` and `T_cost`.

If fewer than `ceil(confidence * N)` replicates hit `q*`, the result is reported
as not certified rather than extrapolated.

## Reporting Rules

Report these separately:

- `T_wall`: certified critical-path wall time to hit `q*`.
- `T_cost`: certified cost proxy to hit `q*`.
- `agent_deliberation_wall_seconds`: LLM reasoning/file-operation time.
- `evaluator_wall_seconds`: training/evaluation wall time.
- `total_steps`: gradient updates completed by each `train.py`.

Do not report LLM-only time as `T_wall`. It is a useful ablation, but the paper's
`T_wall` includes both deliberation and evaluator time.
