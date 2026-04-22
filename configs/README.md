# Config Catalog

This directory intentionally keeps only active or reproducible experiment configs.

## Core

- `models.yaml`: all backend aliases.
- `profiles.yaml`: benchmark profile split. Active paper experiments use three dev profiles and three holdout profiles; `hard_optimization` is legacy.
- `hard_local_smoke.yaml`: deterministic local C(a) smoke for protocol validation.
- `paper_profile_local_validation.yaml`: deterministic local C(a) validation over all active dev/holdout profiles.
- `paper_dev_model_comparison.yaml`: prompt-controlled dev split model comparison, currently Haiku vs Qwen Coder.
- `paper_holdout_final_eval.yaml`: final holdout split model comparison. Do not use this for prompt/model selection or student training.

## Current Real-Model Experiments

- `hard_haiku_prompt_controlled_10step.yaml`: legacy single-profile Haiku C(a) run using the single active prompt, `single_step_program.txt`.
- `hard_qwen_prompt_controlled_10step.yaml`: legacy single-profile Qwen Coder C(a) run using the same single active prompt.
- `hard_single_prompt_model_matrix.yaml`: legacy single-profile one-step model matrix over GPT/Codex, Qwen Coder, Haiku, Sonnet, and Opus aliases using the same single active prompt.

Historical Haiku batch and Qwen direct-edit configs were removed from the active
catalog because they are not prompt-identical experiment entrypoints. Their
validated outputs remain in `runs/` and the retained analysis artifacts.

All active experiment configs that call the orchestrator use
`candidate_generation: batched`; non-batched generation is now rejected by the
orchestrator.

## Teacher, Student, And Analysis

- `phase4_teacher_opus_pilot.yaml`: small Opus teacher pilot over the dev split.
- `phase4_teacher_opus.yaml`: teacher data collection config over the dev split.
- `phase5_routing_student.yaml`: routing-only student training.
- `phase5_routing_student_online.yaml`: online/local routing-student comparison.
- `offline_routing_student.yaml`: classical offline routing experiments.
- `offline_lora_router.yaml`: local LoRA routing classifier.
- `feedback_use_cb.yaml`: local C(b) feedback-use diagnostic with controlled mode selection.

Historical Phase 1/2/3/3.5 configs and superseded one-off smokes were removed to keep the experiment surface small. Their summarized results remain in the project logs and retained artifacts where scientifically relevant.
