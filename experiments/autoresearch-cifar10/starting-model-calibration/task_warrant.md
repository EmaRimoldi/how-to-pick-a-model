# Task Warrant

This experiment chooses the starting `autoresearch/train.py` for later agent
workflow comparisons. It is not itself an agent experiment.

## Why A Starting Model Is Needed

Later experiments will compare workflows such as single-agent, parallel, shared
memory, swarm, and merge. Those comparisons are only meaningful if every
workflow starts from the same file and is scored by the same evaluator.

Without this calibration, an agent result would be hard to interpret:

- if the starting file is already near the best attainable result, most agents
  fail for reasons unrelated to workflow quality;
- if the starting file is obviously broken, trivial edits win and every
  workflow looks competent;
- if the evaluator length changes between analyses, differences can come from
  training budget rather than agent behavior.

The role of this experiment is therefore narrow: select a credible starting
`train.py` that can still be improved by several different kinds of edits.

## What The Task Is

The future agent task is:

1. start from the selected `autoresearch/train.py`;
2. edit that file;
3. train the resulting candidate for **1170 optimizer updates**;
4. score the candidate by validation loss.

An optimizer update is one parameter-update step during training. The number
1170 is not wall-clock time and not an agent reasoning step. It is the fixed
training length used by the evaluator.

The score is validation loss, logged as `val_bpb`. Lower is better. This report
does not use a separate `Q` or `Q*` metric.

## What Counts As Success

The selected starting file scores:

```text
validation loss before any edit: val_bpb = 0.841354
success threshold after an edit: val_bpb <= 0.824
```

An agent edit succeeds only if the trained candidate reaches `val_bpb <= 0.824`
under the same 1170-update evaluator.

The threshold is not arbitrary: it is set so that the task requires a real
improvement over the selected starting file while still being reachable by at
least three independent edit families in the calibration evidence.

## Evidence Used For The Decision

The decision uses the 1170-update calibration runs summarized in:

- [`results/tables/baseline_summary.csv`](results/tables/baseline_summary.csv)
- [`results/tables/trial_results.csv`](results/tables/trial_results.csv)
- [`results/baseline_headroom_summary.md`](results/baseline_headroom_summary.md)

The selected starting model is the candidate described as "width 30, lower
learning rate" and stored internally as `width30_lr_low`.

At 1170 optimizer updates:

- its unedited score is `val_bpb = 0.841354`;
- 4 of 7 predefined edits improved enough to be useful;
- the winning edits came from 3 different families: batch size, learning rate,
  and model capacity;
- several edits failed, including scheduler and optimizer changes, so the task
  is not solved by any arbitrary modification.

## Evidence Not Used For The Decision

The 585-update runs are retained as exploratory/debugging evidence. They are
not used to rank starting models, choose the success threshold, or support later
agent-comparison claims.

Reason: 585 optimizer updates made the task too permissive. Too many simple
edits improved the score, so that setting is weaker evidence for agent workflow
quality.

All decision tables, figures, and future comparisons should therefore use a
consistent evaluator length:

```text
AUTOSEARCH_MAX_STEPS = 1170
```

## What Would Invalidate The Task

The task should be revised if any of the following happens in a fresh rerun:

- the selected starting file no longer reproduces near `val_bpb = 0.841354`;
- the same predefined edit panel no longer contains both successes and failures;
- improvements come from only one narrow edit family;
- evaluator runtime or data preparation changes without being recorded;
- later agent experiments mix 585-update and 1170-update results in the same claim.

## Claim Supported By This Experiment

This experiment supports a limited but important claim:

> The repository has a calibrated, reproducible starting `train.py` for later
> agent workflow comparisons, with a fixed 1170-update evaluator and an explicit
> validation-loss success threshold.

It does not yet claim that any agent workflow is better. That claim requires
separate agent runs starting from this calibrated file.
