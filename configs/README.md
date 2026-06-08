# Config Catalog

This directory intentionally keeps only active or reproducible experiment configs.

## Core

- `models.yaml`: all backend aliases.
- `profiles.yaml`: benchmark profile split. Active paper experiments use three dev profiles and three holdout profiles; `hard_optimization` is legacy.
- `paper_profile_local_validation.yaml`: deterministic local C(a) validation over all active dev/holdout profiles.
- `paper_dev_model_comparison.yaml`: prompt-controlled dev split model comparison.
- `paper_holdout_final_eval.yaml`: final holdout split model comparison. Do not use this for prompt or model selection.

## AutoResearch Real-Model Experiments

AutoResearch-specific configs were consolidated under `autoresearch/configs/`.

- `autoresearch/configs/autoresearch_cifar10_model_routing.yaml`: main AutoResearch model-routing run using the canonical prompt, `autoresearch_program.txt`.
- `autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml`: workload pilot using the same canonical prompt.
- `autoresearch/configs/autoresearch_cifar10_workload_holdout.yaml`: holdout workload evaluation using the same canonical prompt.

Historical Haiku batch and Qwen direct-edit configs were removed from the active
catalog because they are not prompt-identical experiment entrypoints. Their
validated outputs remain in `runs/` and the retained analysis artifacts.

Active AutoResearch real-model configs use one prompt shape and the H=20
`interactive_session` trajectory protocol. Local diagnostics may still use
`single` or `batched`, but they live with the AutoResearch configs.

## Diagnostics

- `feedback_use_cb.yaml`: local C(b) feedback-use diagnostic with controlled mode selection.

SWE-bench configs live inside study folders under `swebench/studies/`; see
`swebench/README.md` for the dedicated layout and entrypoints.

Historical Phase 1/2/3/3.5 configs and superseded one-off runs were removed to keep the experiment surface small.
