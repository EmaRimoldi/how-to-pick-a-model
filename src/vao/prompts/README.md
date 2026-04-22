# Prompt Catalog

The only active C(a) model-generation prompt is:

- `single_step_program.txt`

It is the only model-generation prompt used by batched real-model experiment
configs. It asks for mode probabilities, mode ranking, and all six branch edits
in one JSON response.

Legacy routing-only, per-mode edit, direct-edit, repair, diff, replacement, and
shared-block prompt files have been removed from the active repository. Model
comparisons should differ only in the backend/model transport and model weights,
not in prompt shape or prompt count.

Every new batched run writes the exact rendered prompt to:

- `runs/.../steps/step_XXXX/prompt_snapshot.txt`
- `runs/.../steps/step_XXXX/prompt_snapshot.json`
