# Configs

This folder contains the canonical configs for the
`codex_suite_100_vs_gpt55`.

- `swebench_orchestration_codex_suite_100.yaml`: orchestrated system executor.
- `swebench_codex_suite_workers.yaml`: worker menu used by the orchestration.
- `swebench_codex_suite_workers_neutral.yaml`: neutral worker menu for a lower-bias rerun.
- `swebench_orchestration_gpt55_baseline_100.yaml`: single-worker baseline executor.
- `swebench_gpt55_baseline_worker.yaml`: `gpt-5.5` baseline worker.
- `swebench_orchestration_codex_suite_meta_design.yaml`: provenance for the frozen design.
- `swebench_orchestration_codex_suite_meta_design_neutral.yaml`: cleaner meta-design config where worker aliases are capabilities, not roles.

Worker menus are constraints on the meta-orchestrator. The practitioner-declared
default is a YAML file in this folder. If a future meta-design config leaves
`worker_models` empty and enables official discovery, the meta-orchestrator must
consult only official provider sources, materialize a generated worker YAML, and
then emit one `orchestration` object that references only aliases from that menu.

The pilot/dry-run config was removed to reduce ambiguity: the current launcher
uses the two `*_100.yaml` configs.
