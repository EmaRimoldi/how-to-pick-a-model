# Configs

This folder keeps only neutral inputs for the next SWE-bench design trial.

- `swebench_meta_design_neutral.yaml`: meta-design config for generating a fresh orchestration.
- `swebench_neutral_workers.yaml`: neutral worker menu available to the meta-designer and runtime executor.

Worker menus are constraints on the meta-orchestrator. The practitioner-declared
default is a YAML file in this folder. If a future meta-design config leaves
`worker_models` empty and enables official discovery, the meta-orchestrator must
consult only official provider sources, materialize a generated worker YAML, and
then emit a MetaDesignPackage whose embedded `orchestration_design` references
only aliases from that menu.
Live official discovery is explicit: run the prompt renderer with
`--allow-web-model-discovery`, or pass `--model-discovery-manifest` to replay a
saved provider response without network access.

The pilot/dry-run config was removed to reduce ambiguity: the current launcher
should use a freshly generated design plus an explicit executor config.
