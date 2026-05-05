# Prompt Catalog

The active AutoResearch model-generation prompt is:

- `autoresearch_program.txt`

It is the only prompt used by active AutoResearch real-model configs. It adapts
the original AutoResearch autonomous-experiment instructions to the verifier
orchestrator used in this repository: the model proposes structured edits, while
the framework runs the verifier, promotes/discards candidates, and records
results.

The legacy `single_step_program.txt` prompt remains only for archived
stateful-query experiments and should not be used for new AutoResearch runs.

Every new real-model run writes the exact rendered prompt to:

- `runs/.../steps/step_XXXX/prompt_snapshot.txt`
- `runs/.../steps/step_XXXX/prompt_snapshot.json`
