# SWE-bench Experimental Scaffold

This directory contains a neutral SWE-bench orchestration scaffold. It is not a
completed result bundle.

## Contents

- Neutral 100-instance study inputs under `source/study/`.
- SWE-bench orchestration implementation code under
  `source/implementation/vao_swebench_orchestration/`.
- SWE-bench workspace notes under `source/swebench_README.md`.

## Scope

This scaffold is for future SWE-bench orchestration work. It includes configs,
prompts, neutral worker definitions, a fixed 100-instance input slice, and
orchestration code. It does not include completed run outputs, evaluator
reports, scheduler logs, predictions, traces, or failure analyses.

The file `source/study/data/verified_100/instances_private_metadata.jsonl` is
bookkeeping metadata and must not be injected into solver prompts.

## Not Included

- Completed SWE-bench result reports.
- Generated `runs/`, `evaluations/`, and scheduler-output trees.
- Any resolved/unresolved SWE-bench result counts.

## Read First

- `source/study/README.md`
- `source/study/configs/swebench_meta_design_neutral.yaml`
- `source/implementation/vao_swebench_orchestration/prompt.py`
- `source/implementation/vao_swebench_orchestration/executor.py`
