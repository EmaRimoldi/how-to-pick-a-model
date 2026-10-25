# Starting Model Calibration

Use this before comparing agent workflows. The goal is to choose a starting
`train.py` and success threshold from controlled calibration evidence, not after
seeing agent results.

The calibration is intentionally non-agentic:

- define plausible but mildly improvable starting candidates;
- apply a fixed edit panel across several strategy categories;
- run fixed-length `train.py` evaluations in isolated workspaces;
- select a starting point only if multiple edit families can improve it.

## Command

Cheap smoke test:

```bash
uv run agent-workflow baseline-calibration \
  --train-max-steps 2 \
  --baseline-ids lr_low_no_schedule \
  --edit-ids lr_1p5e3,batch64 \
  --out-dir runs/baseline_headroom_smoke
```

Full calibration starting point:

```bash
uv run agent-workflow baseline-calibration \
  --train-max-steps 1170 \
  --train-time-budget 300 \
  --timeout 900 \
  --out-dir runs/baseline_headroom_calibration_fixed1170
```

The full default panel runs 5 baseline candidates and 10 controlled edits per
candidate, minus no-op edits. On CPU this can take hours at 1170 training
updates. Use
`--baseline-ids` and `--edit-ids` for a smaller calibration batch when iterating.

Broader follow-up batch:

```bash
uv run agent-workflow baseline-calibration \
  --extended-panel \
  --train-max-steps 1170 \
  --train-time-budget 300 \
  --timeout 900 \
  --out-dir runs/baseline_headroom_calibration_extended_fixed1170
```

For custom batches, provide JSON lists of spec objects:

```json
[
  {
    "id": "custom_lr_low",
    "category": "baseline",
    "description": "Custom plausible starting point.",
    "changes": {"LEARNING_RATE": 0.0005, "USE_LR_SCHEDULE": false}
  }
]
```

Then run with `--baselines-json path/to/baselines.json` and/or
`--edits-json path/to/edits.json`.

The script writes:

- `baseline_headroom_plan.json`: exact trial plan;
- `baseline_headroom_results.json`: machine-readable results and gate decision;
- `baseline_headroom_trials.tsv`: flat table for quick inspection;
- `baseline_headroom_report.md`: report generated from the calibration batch.

## Gate

A candidate qualifies only if:

- its starting-point run completes;
- at least 3 distinct strategy categories beat the starting point by `min_delta`;
- the completed-edit success rate is in the default 10-30% band.

If a candidate qualifies, the script proposes `target_val_bpb` as the strictest
threshold that is still hit by the required number of winning categories. If no
candidate qualifies, do not proceed to the confirmatory 2x2; revise the
task/starting point first.

## Default Baseline Candidates

- `lr_low_no_schedule`
- `lr_very_low_no_schedule`
- `narrow_lr_low`
- `no_batchnorm_lr_low`
- `overregularized_lr_low`

Add `--include-current-control` to evaluate the current repo starting point as a
diagnostic control. It is not intended as the final selected candidate.

## Default Edit Categories

- `optimizer_lr`
- `scheduler`
- `normalization_capacity`
- `regularization`
- `data_batch`

These categories are intentionally coarse. They are meant to test whether
multiple types of edits can improve the starting point, not to optimize the
final model.
