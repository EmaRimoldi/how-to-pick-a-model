# Value of work after failure

Status: frozen prospective diagnostic; collection pending. No learned controller.

Question: after a visible failure, does the previous artifact help the next
attempt, and can this benefit be forecast before paying for that attempt?

## Frozen collection

- HumanEval+ v0.1.10 / EvalPlus 0.3.1; same dataset hash as the first pilot.
- Shuffle all 74 tasks with executable public doctests with seed 20261023,
  exclude the first pilot's 24 tasks and `HumanEval/47`, take 30, and reserve
  the remaining 19. The reference preflight found an inconsistent public median
  example in task 47 (expected 15.0 instead of 8.0) before any model call.
  This is a selected public-doctest subset, not the complete benchmark.
- Two fresh Qwen3.5-9B prefixes per task. Keep every initial outcome. Only
  visible failure triggers branches; broader-suite results never enter a prompt,
  feature, task-selection rule, or retry trigger. No manufactured failures.
- For each failed checkpoint, both 9B and 27B get four input conditions:
  task alone; task + code; task + public feedback; task + code + public feedback.
  Use the same solve/revise/discard instruction, two draws per cell, randomized
  order, and the exact same parent artifact/feedback. There is no hidden-state
  continuation or private reasoning access.
- Before any child outcome, query a 9B zero-shot probability forecaster twice:
  task only (knowing that an earlier attempt failed), then full observable state,
  with randomized view order. Each predicts all eight model/condition cells.
  Invalid forecasts remain counted with a predeclared 0.5 fallback.
- All generation uses the first pilot's pinned SiliconFlow FP8 provider,
  temperature 0.6, no reasoning, no provider fallback, no sampler seed,
  maximum 1536 output tokens; input admission ceiling is 32768 tokens.
  Record all messages, receipts, failures, artifacts, forecasts, and evaluations.
- Explicit newly authorized total ceiling: **2 USD**. Do not automatically retry
  uncertain requests. Include forecast calls in collection cost; keep candidate
  verification wall time separate from money. Fixed-arm deployment costs include
  the prefix once and one chosen branch. A forecast-based deployment would also
  pay for its forecasting call. This study does not evaluate such a controller.

## Analysis decided before outcomes

Compare artifact+feedback with fresh, artifact alone with fresh, feedback alone
with fresh, and their factorial interaction separately for each target model.
Average repeated draws within checkpoints, checkpoints within tasks, then tasks.
Use task-cluster bootstrap intervals only with at least five failed tasks;
report insufficient coverage otherwise. Do not treat branch draws as tasks.

Compare prospective Brier scores for task-only versus state forecasts against
the realized individual branch draws, including malformed-forecast fallbacks.
Only fully observed matched checkpoints enter these paired comparisons; retain
and disclose incomplete checkpoints and all their costs. No policy fitting,
post-hoc classifier selection, or stopping based on observed advantage.

This estimates the practical effect of supplying additional context, including
its token cost. There is no token-length-matched irrelevant-context control, so
it does not isolate semantic information from input length/framing. Public
feedback can quote code snippets, so the feedback condition is not guaranteed
to contain zero artifact information. A broader prior-art review and stronger,
untouched evaluation would still be needed for a novelty or general-gain claim.
The 19 reserve tasks remain untouched for a later frozen policy evaluation.

## Reproduction

```bash
uv sync --dev --extra continuation-pilot --frozen
uv run python scripts/run_context_value.py \
  --config experiments/humaneval-plus/context-value/configs/study.json \
  --output runs/context-value-plan
```

Planning makes no model calls. Authorized collection adds `--live --budget-usd 2`
and uses a fresh output directory. Supply the key through `--key-stdin` or the
environment, never CLI arguments/tracked files. Uses the same macOS OS sandbox,
reference preflight, protected feedback channels, and strict billing ledger as
the [initial pilot](../openrouter-continuation-pilot/README.md).

Dataset/task licensing: see the [upstream notices](../openrouter-continuation-pilot/NOTICE.md).
