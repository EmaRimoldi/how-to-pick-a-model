# Starting Model Calibration

**Status**: Active
**Period**: April 14, 2026
**Objective**: choose one controlled `autoresearch/train.py` starting point before comparing agent workflows.

## Task Context

Future agents will edit `autoresearch/train.py`, run the training evaluator,
and try to lower validation loss. The logs call this metric `val_bpb`; lower is
better.

The success threshold for later agent runs is `val_bpb <= 0.824`.

## Research Question

The next agent experiments need a shared starting point. If it is too weak, almost
any edit wins. If it is already too strong, no edit works and the comparison
mostly measures noise.

**Can we choose a starting `train.py` where several distinct edit families can
improve validation loss, without making the task too easy?**

This experiment is deliberately non-agentic: a script applied predefined edits, not
an AI agent choosing what to try.

## What Changed

This experiment added a controlled starting-point calibration tool:

- fixed-step evaluator support with `AUTOSEARCH_MAX_STEPS`;
- isolated workspaces for every 01_baseline/edit trial;
- starting-point and edit panels covering optimizer, learning rate, schedule, capacity, regularization, and batch size;
- JSON/CSV/Markdown outputs for calibration batches;
- cost and hitting-time instrumentation from the preceding protocol work.

The working `autoresearch/train.py` starting point was updated to the selected candidate:

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

## Experiments

| calibration batch | training updates | trials | purpose |
| --- | ---: | ---: | --- |
| `baseline_headroom_calibration_fixed1170` | 1170 | 43 | initial batch over plausible starting points |
| `baseline_headroom_calibration_extended_targeted_fixed1170` | 1170 | 38 | broader model / optimizer / regularization batch |
| `baseline_refinement_custom_fixed585` | 585 | 40 | exploratory/debugging batch, excluded from the decision |
| `baseline_refinement_custom_fixed1170` | 1170 | 40 | intermediate-width / head / mild-dropout refinement |

Total controlled evaluations summarized here: **161**.

Trial counts differ because each batch tested a different candidate/edit panel,
and no-op edits were skipped. Compare normalized edit win rate
(`successful_edits / tested_edits`), not raw trial count. Decision claims use
only 1170-update runs.

## Key Figures

![Task definition](figures/figure-01-baseline-screen-overview.png)

**Figure 1** explains the task. There is no separate `Q` metric in this report:
the quality score is validation loss, `val_bpb`, and lower is better.

![Evidence scope](figures/figure-02-gate-diagnostics.png)

**Figure 2** shows which evidence counts. The decision uses 1170-update runs.
The 585-update runs are kept for debugging context, but they are excluded from ranking,
threshold selection, and future agent-comparison claims.

![Starting point choice](figures/figure-03-category-improvement-heatmap.png)

**Figure 3** compares candidate starting points. The selected one is in the
middle: not too hard, not too easy.

![Recommended baseline detail](figures/figure-04-recommended-baseline-detail.png)

**Figure 4** shows the seven edits tested on the selected starting point. Green
bars reach the success threshold; red bars fail to improve enough.

## Decision

Selected starting point:

```text
starting_model = width 30, lower learning rate
internal_id = width30_lr_low
run = refinement_fixed1170
validation loss before any edit = 0.841354
success threshold after an edit = 0.824
```

Edits that reach the success threshold:

| category | best trial | best val_bpb | improvement |
| --- | --- | ---: | ---: |
| data_batch | `width30_lr_low__data_batch__batch256` | 0.784812 | 0.056542 |
| normalization_capacity | `width30_lr_low__normalization_capacity__width32` | 0.823338 | 0.018016 |
| optimizer_lr | `width30_lr_low__optimizer_lr__lr_1p5e3` | 0.800896 | 0.040458 |

Useful failed edits:

| trial | category | val_bpb | delta vs baseline |
| --- | --- | ---: | ---: |
| `width30_lr_low__scheduler__schedule_on` | scheduler | 0.845433 | -0.004079 |

## Candidate Comparison

| starting point | calibration batch | training updates | starting val_bpb | edits that worked | winning categories | success threshold |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| narrow_lr_low | default_fixed1170 | 1170 | 0.864447 | 4/8 | data_batch, normalization_capacity, optimizer_lr | 0.832826 |
| sgd_baseline | extended_fixed1170 | 1170 | 0.884132 | 3/6 | data_batch, optimizer_lr, regularization | 0.872697 |
| width30_lr_low | refinement_fixed1170 | 1170 | 0.841354 | 4/7 | data_batch, normalization_capacity, optimizer_lr | 0.823338 |
| mild_dropout_no_schedule | extended_fixed1170 | 1170 | 1.065839 | 4/7 | data_batch, optimizer_lr, optimizer_scheduler, regularization | 1.035120 |
| overregularized_lr_low | default_fixed1170 | 1170 | 0.966298 | 5/8 | data_batch, normalization_capacity, optimizer_lr, regularization | 0.899594 |
| no_batchnorm_lr_low | default_fixed1170 | 1170 | 1.078067 | 5/8 | data_batch, normalization_capacity, optimizer_lr | 0.963829 |
| fc96_lr_low | refinement_fixed1170 | 1170 | 0.851718 | 5/7 | data_batch, normalization_capacity, optimizer_lr | 0.834426 |
| dropout005_lr_low | refinement_fixed1170 | 1170 | 0.868005 | 5/7 | data_batch, optimizer_lr, regularization | 0.830335 |

## Why 1170 Updates

The 585-update runs were too permissive: too many simple edits improved the
score. They are useful for debugging context, but weak for comparing
agent workflows. At 1170 updates, the task remains learnable while retaining
failed edits.

## Next Step

Run a small agent pilot on `width30_lr_low`:

```text
fixed-length evaluator
AUTOSEARCH_MAX_STEPS = 1170
serialized evaluator
target_val_bpb = 0.824
separate agent_deliberation_wall_time and evaluator_wall_time
true independent replicates
```

## Artifacts

- Summary table: `tables/baseline_summary.csv`
- Trial table: `tables/trial_results.csv`
- Machine-readable summary: `tables/baseline_headroom_summary.json`
- Legacy raw-table note: the `q3` column means the validation-loss threshold
  implied by the third winning edit family. In code/config this threshold is
  named `target_val_bpb`.
- Source calibration reports remain under `runs/baseline_*`.
