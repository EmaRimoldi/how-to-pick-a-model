# Configs

This folder contains the canonical configs for the
`codex_suite_100_vs_gpt55`.

- `swebench_orchestration_codex_suite_100.yaml`: orchestrated system executor.
- `swebench_codex_suite_workers.yaml`: worker menu used by the orchestration.
- `swebench_orchestration_gpt55_baseline_100.yaml`: single-worker baseline executor.
- `swebench_gpt55_baseline_worker.yaml`: `gpt-5.5` baseline worker.
- `swebench_orchestration_codex_suite_meta_design.yaml`: provenance for the frozen design.

The pilot/dry-run config was removed to reduce ambiguity: the current launcher
uses the two `*_100.yaml` configs.
