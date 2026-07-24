# Starting Model Calibration Summary

Generated after the starting-model calibration batches run on April 14, 2026.

## Experiments Run

| run | training updates | trials | purpose |
| --- | ---: | ---: | --- |
| `runs/baseline_headroom_calibration_fixed1170` | 1170 | 43 | initial batch over plausible starting points |
| `runs/baseline_headroom_calibration_extended_targeted_fixed1170` | 1170 | 38 | broader model / optimizer / regularization batch |
| `runs/baseline_refinement_custom_fixed585` | 585 | 40 | exploratory/debugging batch, excluded from the decision |
| `runs/baseline_refinement_custom_fixed1170` | 1170 | 40 | intermediate-width / head / mild-dropout refinement |

Total controlled training evaluations: 161. These were non-agentic calibration
runs: a script applied predefined edits to `autoresearch/train.py`; no agent
chose the edits.

## Main Finding

The decision uses only 1170-update runs. The 585-update task is retained as
exploratory/debugging evidence, but it is too permissive for later agent
comparisons: many reasonable edits win, so it is less useful for testing whether
an agent workflow actually improves search quality.

The best current candidate is the starting model now described as "width 30,
lower learning rate":

```text
internal_id = width30_lr_low
DEPTH = 3
BASE_CHANNELS = 30
FC_HIDDEN = 128
LEARNING_RATE = 5e-4
USE_LR_SCHEDULE = False
WEIGHT_DECAY = 1e-4
DROPOUT_RATE = 0.0
OPTIMIZER = adam
BATCH_SIZE = 128
AUTOSEARCH_MAX_STEPS = 1170
```

This starting point is not obviously broken: it keeps the original depth, batchnorm,
optimizer family, classifier head, weight decay, dropout, and batch size. It is
only mildly mis-tuned through width, learning rate, and schedule.

## Recommended Candidate

`width30_lr_low` at 1170 training updates:

| metric | value |
| --- | ---: |
| validation loss before edits | 0.841354 |
| edit wins | 4 / 7 |
| winning categories | 3 |
| success threshold from third winning family | 0.823338 |

Winning categories:

| category | best edit | val_bpb | improvement |
| --- | --- | ---: | ---: |
| optimizer_lr | `lr_1p5e3` | 0.800896 | 0.040458 |
| normalization_capacity | `width32` | 0.823338 | 0.018016 |
| data_batch | `batch256` | 0.784812 | 0.056542 |

Negative / near-negative controls:

| edit | category | val_bpb | result |
| --- | --- | ---: | --- |
| `lr_1e3` | optimizer_lr | 0.847634 | worse |
| `adamw_1e3` | optimizer_lr | 0.878075 | worse |
| `schedule_on` | scheduler | 0.845433 | worse |

Recommended success threshold for the next pilot:

```text
target_val_bpb = 0.824
```

`target_val_bpb` is the code/config field for the success threshold. This value
includes the third winning category (`width32`, 0.823338) while still
requiring a real improvement over the baseline (0.841354).

## Why Not the Other Candidates

`narrow_lr_low` at 1170 is a valid backup, but `width30_lr_low` is less
obviously weakened and closer to the current task.

```text
narrow_lr_low:
validation_loss_before_edits = 0.864447
winning categories = optimizer_lr, normalization_capacity, data_batch
raw wins = 4 / 8
target_val_bpb = 0.832826
```

`overregularized_lr_low`, `mild_dropout_no_schedule`, `small_fc_lr_low`, and
`shallow_lr_low` expose multiple winning edit families, but they are too easy or too
obviously damaged. They are useful diagnostics, not the best confirmatory
baseline.

`weak_regularization_no_schedule` is too strong/narrow: only `data_batch` wins.

`width28_lr_low`, `width24_lr_mid`, and `fc96_lr_low` were too permissive at
1170 updates. The 585-update refinements are not decision evidence.

## Decision

Use the `width30_lr_low` starting point with `AUTOSEARCH_MAX_STEPS = 1170` for
the next agent pilot.

Do not use the 585-update evaluator for the confirmatory 2x2. It makes the task
too easy and too dominated by broad early-training improvements.

Before the final 2x2, run a small agentic pilot on `width30_lr_low` with:

```text
target_val_bpb = 0.824
fixed-step evaluator
serialized evaluator
separate evaluator_wall_time and agent_deliberation_wall_time
true independent replicates
```
