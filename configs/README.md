# Config Catalog

This directory intentionally keeps only active or reproducible experiment configs.

## Core

- `models.yaml`: all backend aliases.
- `profiles.yaml`: benchmark profile split. Active paper experiments use three dev profiles and three holdout profiles; `hard_optimization` is legacy.
- `hard_local_smoke.yaml`: deterministic local C(a) smoke for protocol validation.
- `paper_profile_local_validation.yaml`: deterministic local C(a) validation over all active dev/holdout profiles.
- `paper_dev_model_comparison.yaml`: prompt-controlled dev split model comparison.
- `paper_holdout_final_eval.yaml`: final holdout split model comparison. Do not use this for prompt or model selection.

## Current Real-Model Experiments

- `autoresearch_cifar10_model_routing.yaml`: main AutoResearch model-routing run using the canonical prompt, `autoresearch_program.txt`.
- `autoresearch_cifar10_workload_pilot.yaml`: workload pilot using the same canonical prompt.
- `autoresearch_cifar10_workload_holdout.yaml`: holdout workload evaluation using the same canonical prompt.

Historical Haiku batch and Qwen direct-edit configs were removed from the active
catalog because they are not prompt-identical experiment entrypoints. Their
validated outputs remain in `runs/` and the retained analysis artifacts.

Active AutoResearch real-model configs use one prompt shape. Some runs use
`candidate_generation: single` and some smoke/local configs use `batched`; both
are driven by `autoresearch_program.txt`.

## Diagnostics

- `feedback_use_cb.yaml`: local C(b) feedback-use diagnostic with controlled mode selection.
- `swebench_orchestration_smoke.yaml`: first SWE-bench distribution-aware orchestration scaffold using leakage-safe Verified metadata and Codex/GPT-5.5 only as the offline meta-designer.
- `swebench_open_source_workers.yaml`: runtime-only open-source Qwen Coder worker endpoints served through OpenAI-compatible APIs.
- `swebench_orchestration_pilot.yaml`: small patch-generation-only executor pilot over the smoke slice using the open-source worker config.

Historical Phase 1/2/3/3.5 configs and superseded one-off smokes were removed to keep the experiment surface small.
