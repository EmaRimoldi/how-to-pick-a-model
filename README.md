# Verifiable Agentic Optimization for Query-Engine Editing

This repository implements the experimental framework for the NeurIPS-oriented verifiable agentic optimization protocol described in `docs/`.

The canonical task is iterative editing of a Python `solution.py` implementing `CandidateQueryEngine`. At every step the agent must produce an explicit probability distribution over six modes and one candidate edit for each mode:

- `layout`
- `indexing`
- `topk`
- `caching`
- `summaries`
- `micro`

All six branches are evaluated offline by the verifier. In the default `top1_only` visibility regime, only the branch selected by the model's own top-probability mode is promoted to the next online state, while all counterfactual branch results are logged for analysis.

## Quick Start

Run the local deterministic smoke protocol:

```bash
PYTHONPATH=src:. python -m vao.orchestrator --config configs/phase1_dev.yaml --models local_stub --profiles paper_development --steps 2
PYTHONPATH=src:. python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv
PYTHONPATH=src:. python -m vao.training.build_routing_dataset --runs runs/phase1_dev --train_out artifacts/routing_train.jsonl --dev_out artifacts/routing_dev.jsonl
pytest -q
```

Every run writes a self-contained directory containing `run_manifest.json`, `baseline_verification.json`, `evaluations.jsonl`, `run_summary.json`, resolved config, step branch workspaces, verifier outputs, and candidate source snapshots.

For real Claude/Anthropic runs, candidate generation is protocol-configurable. Phase 3.5 validated a patch mode where the model returns one `unified_diff` per mode, saved as `model_edit.diff` and materialized into `proposed_solution.py`. The production protocol for teacher-data generation is the validated replacement-file C(a) protocol because it is currently faster and more reliable than patch mode.

## Main Entry Points

- `python -m vao.orchestrator --config configs/phase1_dev.yaml`
- `python -m vao.verifier --smoke_test`
- `python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv`
- `python -m vao.training.build_routing_dataset --runs runs/phase1_dev --train_out artifacts/routing_train.jsonl --dev_out artifacts/routing_dev.jsonl`
- `python -m vao.validate_run --run_dir runs/phase2_dev/<run_id>`
- `python -m vao.orchestrator --config configs/phase3_haiku_smoke.yaml --models claude_haiku --profiles paper_development --steps 2`
- `python -m vao.analysis.phase3_summary --runs runs/phase35_patch/haiku_dev --summary_out artifacts/phase35_patch_summary.json --failure_modes_out artifacts/phase35_patch_failure_modes.json`
- `python -m vao.orchestrator --config configs/phase4_teacher_opus_pilot.yaml --models claude_opus_teacher --steps 3`
- `python -m vao.training.build_routing_dataset --runs runs/phase4_teacher_opus_pilot runs/phase4_teacher_opus --out artifacts/phase4_teacher_routing_dataset.jsonl`
- `python -m vao.training.train_routing_lora --config configs/phase5_routing_student.yaml`
- `python -m vao.orchestrator --config configs/phase5_routing_student_online.yaml --models local_stub,routing_student --steps 3`
- `python -m vao.analysis.dataset_audit --dataset artifacts/phase4_teacher_routing_dataset.jsonl --json_out artifacts/offline_routing_dataset_audit.json --md_out artifacts/offline_routing_dataset_audit.md`
- `python -m vao.analysis.replay_routing --dataset artifacts/phase4_teacher_routing_dataset.jsonl --student_model training/phase5_routing_student/model.pkl --json_out artifacts/replay_router_comparison.json --md_out artifacts/replay_router_comparison.md`
- `python -m vao.training.offline_routing_experiments --config configs/offline_routing_student.yaml`
- `python -m vao.training.lora_smoke --out artifacts/local_lora_smoke.json --env_out artifacts/local_training_stack_audit.json`
- `python -m vao.training.train_local_lora_router --config configs/offline_lora_router.yaml`
- `python -m vao.orchestrator --config configs/feedback_use_cb.yaml --run-id cb_local_fixed_micro`
- `python -m vao.analysis.run_diagnostics_visuals --run_dir runs/feedback_use_cb/cb_local_fixed_micro --single_mode micro`

The closed-source and open-weight model adapters are scaffolded behind the same interface as the deterministic `local_stub` backend. `claude_haiku` is the first real backend. It can use `ANTHROPIC_API_KEY` through the Messages API or the authenticated Claude CLI transport when available. Normal tests use fixtures and do not require live model calls.

## Current Milestone Status

- Production teacher-data protocol is frozen as C(a) replacement-file candidate generation.
- Opus teacher pilot produced 3 validated runs, 9 steps, and 54 branch evaluations.
- Production Opus collection was attempted under `runs/phase4_teacher_opus/`; the first run produced 3 validated steps before `claude_cli_failed:1` stopped further collection.
- Claude quota is currently unavailable, so current work is offline only: no Claude, Opus, Haiku, or new teacher generation.
- The existing teacher routing dataset has 12 examples. It is useful for tooling and failure analysis, but it is too small and imbalanced for a strong learned-routing claim.
- The strongest current classical offline student is `tfidf_word_multinomial_nb` selected by leave-one-out expected regret. `always_layout` is still the best replay baseline by expected regret because `layout` dominates productive labels.
- The local training stack now includes `peft` and `trl`; a toy LoRA smoke test passed, and a cached `distilbert-base-uncased` LoRA router was trained locally. It overfits toward `layout` and does not beat the classical/replay baselines on the tiny split.
- C(b) feedback-use infrastructure is implemented for local/offline validation: set `feedback_condition: cb`, `visibility_regime: all_branches`, and `ask_post_feedback_distribution: true`. Controlled promotion is available through `selection_policy: fixed_mode` or `mode_sequence`.
- Per-run diagnostics plots are available for mode probabilities, single-mode trajectories, loss by mode, gain heatmaps, and cost per step under `artifacts/plots/run_<run_id>/`.
- Offline student eval on the tiny split improved regret/JSD versus the original teacher route on that split, but the online local controlled experiment was worse than the local-stub router. Treat Phase 5 as infrastructure plus a negative first result, not as evidence of a useful student yet.
