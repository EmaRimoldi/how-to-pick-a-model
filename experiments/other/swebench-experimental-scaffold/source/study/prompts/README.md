# Prompt Templates

This directory separates design-time prompting from runtime solver prompting.

- `meta_designer_prompt_template.txt` is the design-time prompt. It asks the
  meta-designer to produce a MetaDesignPackage from the allowed worker menu,
  public instance slice, available tools, and deployment loss objective. The
  package contains distribution analysis, candidate policies, loss estimates,
  selection rationale, and one clean executor-facing orchestration design.
- `runtime_component_prompt_template.md` documents the runtime prompt assembled
  by the executor for each component call.

The actual runtime prompt rendering lives in
`swebench/src/vao/swebench_orchestration/executor.py` in
`_render_component_prompt()`. Patch-producing components must return JSON with
`model_patch` set to a SWE-bench-compatible unified diff. Router, localizer, and
reviewer-style components return structured observations for downstream
components.
