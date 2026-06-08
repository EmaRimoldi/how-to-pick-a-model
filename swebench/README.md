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

## Codex-suite comparison

The Codex-suite single-orchestration experiment and matched `gpt-5.5` baseline
are wired through:

```bash
bash swebench/scripts/submit_codex_suite_100_vs_gpt55_slurm.sh
```

That job uses Codex CLI workers, materializes SWE-bench checkouts before patch
generation, evaluates predictions with the local no-Docker verifier, and writes
the comparison to
`swebench/studies/codex_suite_100_vs_gpt55/runs/<run_id>/comparison_summary.json`.
