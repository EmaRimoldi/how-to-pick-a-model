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

The active benchmark now uses a single canonical profile: `hard_optimization`. It combines all workload families into one difficult mixed profile so new experiments no longer spread across separate development/holdout/profile variants.

## Quick Start

Run the local deterministic smoke protocol:

```bash
PYTHONPATH=src:. python -m vao.orchestrator --config configs/hard_local_smoke.yaml --run-id hard_local_smoke
PYTHONPATH=src:. python -m vao.validate_run --run_dir runs/hard_profile/local_smoke/hard_local_smoke
PYTHONPATH=src:. python -m vao.analysis.compute_estimators --runs runs/hard_profile/local_smoke/hard_local_smoke --out artifacts/hard_local_smoke_estimators.csv
PYTHONPATH=src:. python -m vao.training.build_routing_dataset --runs runs/hard_profile/local_smoke/hard_local_smoke --out artifacts/hard_local_smoke_routing_dataset.jsonl
pytest -q
```

Or run the same local smoke through the helper script:

```bash
scripts/run_hard_profile_smoke.sh
```

To additionally run the one-step Haiku batch smoke, use:

```bash
RUN_HAIKU=1 scripts/run_hard_profile_smoke.sh
```

Every run writes a self-contained directory containing `run_manifest.json`, `baseline_verification.json`, `evaluations.jsonl`, `run_summary.json`, resolved config, step branch workspaces, verifier outputs, and candidate source snapshots.

For real Claude/Anthropic runs, candidate generation is protocol-configurable. Phase 3.5 validated a `unified_diff` patch mode, but it was slower and less reliable than replacement files because diff application and repair failed too often. The current default for future Claude runs is `structured_edits`: the model returns compact exact edits such as `replace_exact` or `replace_function`, the harness applies them to six branch-local copies, and the verifier still evaluates full materialized `proposed_solution.py` files.

The fastest current Haiku path is the batched structured-edit variant: one model call returns `mode_probs`, `mode_ranking`, and six mode-constrained structured edits. Use `candidate_generation: batched` or `configs/phase3_haiku_structured_batch_smoke.yaml` for that path. The one-step speed smoke passed validation, but one candidate was rejected and logged as a no-op, so this needs a larger quality smoke before teacher-data scaling.

## Active Benchmark Profile

`hard_optimization` is intentionally hard to optimize with a single obvious edit. It uses:

- 2,600 initial items
- 120,000-key space
- 1,200 operations per trace
- 1 trace per workload family
- all nine workload families: point reads, hot keys, bursty updates, local ranges, distribution shifts, wide ranges, repeated windows, top-k stress, and negative lookup churn
- 2 measurement repetitions with 120 warmup operations

This profile creates real tradeoffs between layout, indexing, summaries, caching, top-k specialization, and micro-optimization. Historical artifacts may still contain older profile names, but new configs point to `hard_optimization`.

## Main Entry Points

- `python -m vao.orchestrator --config configs/phase1_dev.yaml`
- `python -m vao.orchestrator --config configs/hard_local_smoke.yaml --run-id hard_local_smoke`
- `python -m vao.orchestrator --config configs/hard_haiku_batch_smoke.yaml --run-id hard_haiku_batch_smoke`
- `OPENAI_COMPATIBLE_BASE_URL=http://localhost:8000/v1 RUN_ID=hard_qwen_batch_smoke_1step scripts/run_qwen_smoke.sh`
- `python -m vao.verifier --smoke_test`
- `python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv`
- `python -m vao.training.build_routing_dataset --runs runs/phase1_dev --train_out artifacts/routing_train.jsonl --dev_out artifacts/routing_dev.jsonl`
- `python -m vao.validate_run --run_dir runs/phase2_dev/<run_id>`
- `python -m vao.orchestrator --config configs/phase3_haiku_smoke.yaml --models claude_haiku --profiles hard_optimization --steps 2`
- `python -m vao.orchestrator --config configs/phase3_haiku_structured_batch_smoke.yaml --models claude_haiku_batch --profiles hard_optimization --steps 1`
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
- `python -m vao.analysis.run_diagnostics_visuals --run_dir runs/hard_profile/haiku_batch_smoke/hard_haiku_batch_smoke_1step --single_mode indexing`

The closed-source and open-weight model adapters share the same interface as the deterministic `local_stub` backend. `claude_haiku` can use `ANTHROPIC_API_KEY` through the Messages API or the authenticated Claude CLI transport when available. `weak_qwen` now targets an OpenAI-compatible `/v1/chat/completions` endpoint, such as vLLM/SGLang or the minimal `scripts/qwen_openai_compat_server.py` smoke server. Normal tests use fixtures/mocks and do not require live model calls.

## Qwen Smoke Setup

For an Engaging GPU smoke, the tested path was:

```bash
ssh engaging
salloc -p mit_preemptable -t 01:00:00 -c 8 --mem=32G --gres=gpu:l40s:1
module load miniforge/25.11.0-0 cuda/12.9.1
python -m pip install --user --upgrade 'transformers>=4.46' accelerate sentencepiece safetensors
python ~/vao_qwen_smoke/qwen_openai_compat_server.py \
  --model Qwen/Qwen2.5-Coder-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16
```

Then tunnel `localhost:8000` to the compute node, replacing `node1632` with the allocated node:

```bash
ssh -N -L 8000:node1632:8000 engaging
```

Run locally:

```bash
RUN_ID=hard_qwen_batch_smoke_1step \
OPENAI_COMPATIBLE_BASE_URL=http://localhost:8000/v1 \
scripts/run_qwen_smoke.sh
```

## Current Milestone Status

- Future teacher-data protocol should use C(a) with `structured_edits` candidate generation. Replacement-file and unified-diff protocols remain available as legacy fallbacks.
- Opus teacher pilot produced 3 validated runs, 9 steps, and 54 branch evaluations.
- Production Opus collection was attempted under `runs/phase4_teacher_opus/`; the first run produced 3 validated steps before `claude_cli_failed:1` stopped further collection.
- Claude quota is currently unavailable, so current work is offline only: no Claude, Opus, Haiku, or new teacher generation.
- The existing teacher routing dataset has 12 examples. It is useful for tooling and failure analysis, but it is too small and imbalanced for a strong learned-routing claim.
- The strongest current classical offline student is `tfidf_word_multinomial_nb` selected by leave-one-out expected regret. `always_layout` is still the best replay baseline by expected regret because `layout` dominates productive labels.
- The local training stack now includes `peft` and `trl`; a toy LoRA smoke test passed, and a cached `distilbert-base-uncased` LoRA router was trained locally. It overfits toward `layout` and does not beat the classical/replay baselines on the tiny split.
- C(b) feedback-use infrastructure is implemented for local/offline validation: set `feedback_condition: cb`, `visibility_regime: all_branches`, and `ask_post_feedback_distribution: true`. Controlled promotion is available through `selection_policy: fixed_mode` or `mode_sequence`.
- Per-run diagnostics plots are available for mode probabilities, single-mode trajectories, loss by mode, gain heatmaps, and cost per step under `artifacts/plots/run_<run_id>/`.
- Edit-protocol diagnostics are in `artifacts/edit_protocol_debug_report.md`. Observed replacement outputs were around 3.7k raw chars/candidate; a structured one-line edit example is 219 chars and a structured function edit example is 533 chars.
- Batched Haiku speed diagnostics are in `artifacts/haiku_batch_speed_debug_report.md`: 132.7 seconds/step and `$0.179`/step on the one-step batch smoke, versus 480.4 seconds/step for six separate structured-edit calls and 326.4 seconds/step for the historical replacement smoke.
- Hard-profile readiness diagnostics are in `artifacts/hard_profile_experiment_readiness.md`. The validated Haiku batch full-profile smoke took 346.4 seconds total for one step including baseline, cost `$0.171`, and had zero proposal/verifier failures.
- The first 3-step hard Haiku batch pilot is summarized in `artifacts/hard_haiku_batch_pilot_readout.md`: 18 branch evaluations, 807.0s total wall-clock, `$0.600` total cost, and validated C(a) logs.
- Qwen smoke is validated through `weak_qwen` with `Qwen/Qwen2.5-Coder-1.5B-Instruct` served on Engaging. The one-step hard-profile run completed in 240.9s, produced 6 branch evaluations, and passed `vao.validate_run`.
- Offline student eval on the tiny split improved regret/JSD versus the original teacher route on that split, but the online local controlled experiment was worse than the local-stub router. Treat Phase 5 as infrastructure plus a negative first result, not as evidence of a useful student yet.
