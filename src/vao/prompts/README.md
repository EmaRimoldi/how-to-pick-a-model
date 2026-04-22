# Prompt Catalog

The active C(a) experiment prompt is:

- `single_step_program.txt`

It is the only model-generation prompt used by batched real-model experiment
configs. It asks for mode probabilities, mode ranking, and all six branch edits
in one JSON response.

Other prompt files are retained for legacy tests, repair experiments, routing
students, and C(b)/diagnostic paths. They are not active entrypoints for the
current prompt-controlled Haiku/Qwen/GPT comparisons.

Every new batched run writes the exact rendered prompt to:

- `runs/.../steps/step_XXXX/prompt_snapshot.txt`
- `runs/.../steps/step_XXXX/prompt_snapshot.json`
