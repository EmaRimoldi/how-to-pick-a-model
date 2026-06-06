# SWE-Bench workspace

This directory is the dedicated umbrella for SWE-Bench work inside `NeurIPS_2026`.

## Intended layout

- `runs/` — durable run outputs, logs, traces, and predictions worth keeping
- `runtime/` — fallback local runtime cache/venv when not running inside Slurm
- `meta_design/` — optional future home for frozen orchestration bundles
- `datasets/` — optional future home for copied/curated SWE-Bench slices

## Quota policy

When running on Slurm, heavyweight ephemeral assets should prefer node-local scratch via
`$SLURM_TMPDIR` rather than `/home`:

- Hugging Face cache
- temporary vLLM virtualenv
- other throwaway bootstrap files

The launcher `scripts/run_swebench_orchestration_slurm_pilot.sh` is configured to default to
`$SLURM_TMPDIR/swebench_runtime/` for those ephemeral assets when available.
