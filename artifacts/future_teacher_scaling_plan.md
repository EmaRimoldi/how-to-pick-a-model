# Future Teacher Scaling Plan

This plan is prepared for when Claude/Anthropic quota returns. Do not run it during quota pause.

## Current Protocol

- Protocol: C(a), structured edit candidate outputs.
- Backend config: `claude_opus_teacher`.
- Run config: `configs/phase4_teacher_opus.yaml`.
- First action after quota returns: run one 2-step structured-edit smoke on `hard_balanced_dev` and validate before launching the dev matrix.

## Target Matrix

- Dev teacher collection: 3 profiles x 3 repeats x 5 steps = `45` steps.
- Holdout teacher-style evaluation is not for training: 3 profiles x 2 repeats x 5 steps = `30` steps, run only after model/protocol choices are frozen.
- Total with final holdout evaluation: `75` steps.

## Cost and Time Projection

- Observed Opus average cost/step: `$1.7797780625000001`.
- Observed Opus average wall-clock/step: `643.0542123052809` seconds.
- Dev-only projected cost: `$80.09`.
- Dev-only serial wall-clock: `8.04` hours.
- Dev+holdout projected cost: about `$133.48`.
- Dev+holdout serial wall-clock: about `13.40` hours.

## Resume Checklist

1. Confirm Claude CLI/API quota is available.
2. Run one 2-step Opus `structured_edits` smoke and validate.
3. Launch one profile/repeat at a time so partial failures remain usable.
4. Validate each run with `python -m vao.validate_run --run_dir <RUN_DIR>`.
5. Rebuild `artifacts/phase4_teacher_routing_dataset.jsonl` from validated dev runs only, using `--exclude_holdout`.
6. Re-run offline audit, replay leaderboard, and routing-student training.

## Target Dataset Size

- Minimum next target: 45 validated dev routing examples.
- Preferred next target with separate holdout evaluation: 75 validated examples, but only the 45 dev examples should enter post-training.
- Routing-only claims should wait until all six productive modes have nonzero labels and no mode has fewer than 5 examples.
