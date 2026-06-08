# Prompt Catalog

This shared prompt package only retains the legacy `single_step_program.txt`
prompt for archived stateful-query experiments.

Active AutoResearch prompts live in `autoresearch/prompts/`:

- `autoresearch_program.txt`
- `autoresearch_router.txt`
- `autoresearch_allocation_router.txt`

Every new real-model run writes the exact rendered prompt to:

- `runs/.../steps/step_XXXX/prompt_snapshot.txt`
- `runs/.../steps/step_XXXX/prompt_snapshot.json`
