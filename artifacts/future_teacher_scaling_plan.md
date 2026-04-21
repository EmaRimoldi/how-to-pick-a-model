# Future Teacher Scaling Plan

This plan is prepared for when Claude/Anthropic quota returns. Do not run it during quota pause.

## Current Protocol

- Protocol: C(a), structured edit candidate outputs.
- Backend config: `claude_opus_teacher`.
- Run config: `configs/phase4_teacher_opus.yaml`.
- Fallback backend config: `claude_opus_teacher_replacement_legacy`.
- First action after quota returns: run a 1-profile, 2-step structured-edit smoke and validate before launching the matrix.

## Target Matrix

- Dev: 3 profiles x 3 repeats x 5 steps = `45` steps.
- Optional holdout: 2 profiles x 2 repeats x 5 steps = `20` steps.
- Total with holdout: `65` steps.

## Cost and Time Projection

- Observed Opus average cost/step: `$1.7797780625000001`.
- Observed Opus average wall-clock/step: `643.0542123052809` seconds.
- Dev-only projected cost: `$80.09`.
- Dev-only serial wall-clock: `8.04` hours.
- Dev+holdout projected cost: `$115.69`.
- Dev+holdout serial wall-clock: `11.61` hours.

## Resume Checklist

1. Confirm Claude CLI/API quota is available.
2. Run one 2-step Opus `structured_edits` smoke and validate.
3. Launch one profile/repeat at a time so partial failures remain usable.
4. Validate each run with `python -m vao.validate_run --run_dir <RUN_DIR>`.
5. Rebuild `artifacts/phase4_teacher_routing_dataset.jsonl` from validated runs only.
6. Re-run offline audit, replay leaderboard, and routing-student training.

## Target Dataset Size

- Minimum next target: 45 validated dev routing examples.
- Preferred next target with holdout: 65 validated examples.
- Routing-only claims should wait until all six productive modes have nonzero labels and no mode has fewer than 5 examples.
