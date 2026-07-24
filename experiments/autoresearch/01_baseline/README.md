# Starting Model Calibration

**Status**: Active
**Date**: April 14, 2026
**Purpose**: choose one controlled `autoresearch/train.py` starting point before
comparing agent workflows.

Read [`task_warrant.md`](task_warrant.md) first if you want the rationale for
the task and the 1170-update evaluator.

## Why This Exists

Future experiments ask whether different agent workflows can improve a small ML
training script. For that comparison to mean anything, every workflow must start
from the same `train.py`.

The starting point cannot be arbitrary:

- if it is already too good, few useful improvements remain;
- if it is too broken, improvements are obvious and the task is too easy;
- if it is unstable, differences between agents may just be evaluator noise.

This experiment chooses a middle starting point: credible, reproducible, and still
improvable in more than one way.

## Task In One Sentence

An agent will edit `autoresearch/train.py`; the evaluator will train it for
1170 optimizer updates; the result is scored by validation loss.

Lower validation loss is better. In the logs this value is named `val_bpb`.
An optimizer update is one parameter-update step during training. It is not an
agent reasoning step and not wall-clock time.

## What Was Run

This was not an agent experiment. A script applied predefined edits to candidate
starting files and measured what happened.

- **161** controlled evaluator runs.
- **4** calibration batches.
- **1170** optimizer updates for all decision evidence.
- **585** optimizer-update runs retained only as exploratory/debugging
  evidence.
- Edits covered batch size, learning rate, model capacity, schedule, optimizer,
  and regularization.

Trial counts differ because each calibration batch tested a different set of
candidates and edits. The decision therefore uses **edit success rate**:
successful edits divided by tested edits, restricted to 1170-update runs.

## Result

The selected starting point is:

```text
human description: width 30, lower learning rate
internal id:        width30_lr_low
training length:   1170 optimizer updates
score before edit: val_bpb = 0.841354
success threshold: val_bpb <= 0.824
```

Why this one:

- 4 of 7 simple edits improved it;
- improvements came from 3 different edit families;
- some edits failed, so the task is not a free win;
- the starting file is still a plausible training setup, not an obviously
  damaged toy.

## How To Read The Figures

![Task definition](results/figures/figure-01-baseline-screen-overview.png)

**Figure 1** explains the task. There is no separate `Q` metric in this report:
the quality score is validation loss, `val_bpb`, and lower is better.

![Evidence scope](results/figures/figure-02-gate-diagnostics.png)

**Figure 2** shows which evidence counts. The decision uses 1170-update runs.
The 585-update runs are kept for debugging context, but they are excluded from ranking,
threshold selection, and future agent-comparison claims.

![Starting point choice](results/figures/figure-03-category-improvement-heatmap.png)

**Figure 3** compares candidate starting points. The selected one is in the
middle: not too hard, not too easy.

![Edit outcomes](results/figures/figure-04-recommended-baseline-detail.png)

**Figure 4** shows the seven edits tested on the selected starting point. Green
bars reach the success threshold; red bars fail to improve enough.

![Edit family summary](results/figures/figure-06-presentation-width30-detail.png)

**Figure 5** shows that three independent edit families can reach the success
threshold:
batch size, learning rate, and model capacity.

## Selected `train.py` Settings

```text
DEPTH = 3
BASE_CHANNELS = 30
FC_HIDDEN = 128
OPTIMIZER = adam
LEARNING_RATE = 5e-4
WEIGHT_DECAY = 1e-4
DROPOUT_RATE = 0.0
USE_LR_SCHEDULE = False
BATCH_SIZE = 128
AUTOSEARCH_MAX_STEPS = 1170
```

## Edits That Reach The Success Threshold

| edit family | best edit | validation loss | improvement |
| --- | --- | ---: | ---: |
| Batch size | use batch size 256 | 0.784812 | 0.056542 |
| Learning rate / optimizer | raise learning rate to 0.0015 | 0.800896 | 0.040458 |
| Model capacity | make the model slightly wider | 0.823338 | 0.018016 |

## Useful Failed Edits

These failures matter because they show the task is not automatically solved by
any change.

| edit | family | validation loss | effect |
| --- | --- | ---: | --- |
| turn on learning-rate schedule | Schedule | 0.845433 | worse by 0.004079 |
| raise learning rate to 0.001 | Learning rate / optimizer | 0.847634 | worse by 0.006280 |
| switch optimizer to AdamW | Learning rate / optimizer | 0.878075 | worse by 0.036721 |

## Why 585 Updates Are Not Used For Claims

The 585-update runs were too permissive: too many simple edits improved the
model. They are useful for debugging context, but weak for evaluating
agent workflows.

All decision analysis therefore uses 1170 optimizer updates. Do not mix 585 and
1170 runs in the same claim.

## Next Step

Run a small agent pilot from this exact starting point:

```text
starting train.py: AUTOSEARCH_MAX_STEPS = 1170
success condition: val_bpb <= 0.824
evaluator: serialized when multiple agents share one machine
report separately: agent thinking time and evaluator training time
```

## Artifacts

- Summary table: `results/tables/baseline_summary.csv`
- Trial table: `results/tables/trial_results.csv`
- Machine-readable summary: `results/tables/baseline_headroom_summary.json`
- Figure generator: `../../scripts/plot_baseline.py`

Legacy note: some raw tables still use historical names such as
`baseline_headroom`, `q3`, and `q_star`. In this README, those mean starting
model calibration and success-threshold validation loss.
