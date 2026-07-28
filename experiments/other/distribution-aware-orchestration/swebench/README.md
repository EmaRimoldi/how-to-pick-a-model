# SWE-Bench workspace

This directory is the dedicated umbrella for SWE-Bench work inside `NeurIPS_2026`.

## Intended layout

- `studies/` — per-experiment bundles containing configs, prompts, data, runs, and evaluations
- `src/` — SWE-bench Python modules exposed as `vao.swebench_orchestration`
- `scripts/` — storage checks and Slurm launchers
- `tests/` — SWE-bench-specific tests and fixtures
- `runtime/` — fallback local runtime cache/venv when not running inside Slurm
- `datasets/` — optional future home for copied/curated SWE-Bench slices

## Quota policy

When running on Slurm, heavyweight ephemeral assets should prefer node-local scratch via
`$SLURM_TMPDIR` rather than `/home`:

- Hugging Face cache
- temporary vLLM virtualenv
- other throwaway bootstrap files

The launcher `swebench/scripts/run_swebench_orchestration_slurm_pilot.sh` is configured to default to
`$SLURM_TMPDIR/swebench_runtime/` for those ephemeral assets when available.

## Neutral Trial Setup

The active 100-instance study keeps the dataset slice, neutral worker menu,
prompt templates, and loss weights, but does not keep a frozen orchestration
from a previous run. Generate a fresh design through the meta-design config, then
run it with the generic executor/evaluator entrypoints.
