# Runtime Component Prompt Template

The executor builds one prompt per component call. The template is implemented
in `swebench/src/vao/swebench_orchestration/executor.py` by
`_render_component_prompt()`.

Each runtime prompt includes:

- component id, role, prompt summary, and output contract;
- call index and orchestration id;
- objective summary, routing policy, evidence policy, patch policy, and
  verification policy from the frozen orchestration design;
- repository checkout path when materialized;
- current runtime limitations;
- public SWE-bench instance JSON;
- prior component outputs;
- JSON output instruction for observation or patch-producing components.

Patch and fallback components must return JSON with `model_patch` set to a
unified diff suitable for SWE-bench `predictions.jsonl`. Router, localizer, and
reviewer-style components return structured observations.
