# Config Catalog

This directory contains Agent Workflow runtime config plus the backend catalogs
needed by the imported AutoResearch reproduction harness.

## Agent Workflow

- `experiment.yaml`: editable live-run config for Agent Workflow CLI commands.
- `agent_roster_example.yaml`: example N-agent roster.
- `agent_default.json` and `experiment_default.json`: lightweight defaults used
  by older runtime helpers.

## AutoResearch Reproduction

- `models.yaml`: backend aliases used by the AutoResearch compatibility runtime.
- `profiles.yaml`: profile split catalog used by the compatibility runtime.

For the current AutoResearch model-routing experiment, the canonical worker menu
is:

- `gpt_5_3_codex`
- `gpt_5_4`
- `gpt_5_4_mini`

Historical aliases may remain in `models.yaml` so old config snapshots can still
be interpreted, but they are not part of the current model-routing config unless
explicitly listed under `autoresearch/configs/`.
