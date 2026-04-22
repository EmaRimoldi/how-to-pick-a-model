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

The active paper benchmark now uses three difficult task families with separate development and holdout instances. Development profiles are used for debugging, model selection, and post-training data; holdout profiles are reserved for final generalization checks. The older `hard_optimization` profile is retained only for historical reproducibility.

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

To validate the paper dev/holdout profile split without any live model calls:

```bash
scripts/run_paper_profile_validation.sh
```

This runs six local C(a) smoke runs, validates every run, writes
`artifacts/profile_split_audit.*`, and builds both all-profile and dev-only
routing datasets.

Every run writes a self-contained directory containing `run_manifest.json`, `baseline_verification.json`, `evaluations.jsonl`, `run_summary.json`, resolved config, step branch workspaces, verifier outputs, and candidate source snapshots.

For real-model C(a) runs, the active prompt is a single program:
`src/vao/prompts/single_step_program.txt`. Each step uses one model-generation
prompt that asks for `mode_probs`, `mode_ranking`, and all six branch edits in
one JSON response. The modes are experimental labels, not edit permissions: a
candidate may modify any part of `CandidateQueryEngine` needed for a coherent
implementation, while `primary_mode` records the dominant optimization idea.
Every new batched run stores the exact rendered prompt under
`steps/step_XXXX/prompt_snapshot.txt` and `prompt_snapshot.json`.

Phase 3.5 validated a `unified_diff` patch mode, but it was slower and less
reliable than structured edits because diff application and repair failed too
often. The current production path is `structured_edits`: the model returns
compact operations such as `replace_exact` or `replace_function`, the harness
applies them to six branch-local copies, and the verifier evaluates full
materialized `proposed_solution.py` files. The historical Haiku-vs-Qwen R0-R4
comparison used different generation backends and should be treated as a
model-plus-backend comparison. New prompt-controlled comparisons should use the
paired `hard_haiku_prompt_controlled_10step.yaml` and
`hard_qwen_prompt_controlled_10step.yaml` configs, or
`hard_single_prompt_model_matrix.yaml`.

## Active Benchmark Profiles

The active paper split is defined in `configs/profiles.yaml` and
`benchmarks/stateful_query_engine/metadata/instance_config.json`.

- Dev: `hard_balanced_dev`, `hard_range_dev`, `hard_churn_dev`
- Holdout: `hard_balanced_holdout`, `hard_range_holdout`, `hard_churn_holdout`
- Smoke: `hard_balanced_dev`
- Legacy: `hard_optimization`

The three task families cover balanced mixed workloads, range/summary-heavy
workloads, and churn/top-k/update-heavy workloads. Each task has a dev instance
and a holdout instance with different seeds and scale. Holdout should not be
used for training or prompt/model selection.

## Main Entry Points

- `python -m vao.orchestrator --config configs/hard_local_smoke.yaml --run-id hard_local_smoke`
- `scripts/run_paper_profile_validation.sh`
- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/paper_dev_model_comparison.yaml --steps 10 --run-id paper_dev_r0`
- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/paper_holdout_final_eval.yaml --steps 10 --run-id paper_holdout_final`
- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/hard_haiku_prompt_controlled_10step.yaml --profiles hard_optimization --steps 10 --run-id hard_haiku_single_prompt_10step_r0`
- `PYTHONPATH=src:. OPENAI_COMPATIBLE_BASE_URL=http://localhost:8000/v1 python -m vao.orchestrator --config configs/hard_qwen_prompt_controlled_10step.yaml --profiles hard_optimization --steps 10 --run-id hard_qwen_single_prompt_10step_r0`
- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/hard_single_prompt_model_matrix.yaml --models gpt_5_4_batch_strict --profiles hard_optimization --steps 1 --run-id hard_gpt_5_4_single_prompt_smoke`
- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/hard_single_prompt_model_matrix.yaml --models claude_haiku_batch_strict,claude_sonnet_batch_strict --profiles hard_optimization --steps 1 --run-id hard_claude_single_prompt_smoke`
- `python -m vao.verifier --smoke_test`
- `python -m vao.orchestrator --config configs/phase4_teacher_opus_pilot.yaml --models claude_opus_teacher --steps 3`
- `python -m vao.training.build_routing_dataset --runs runs/phase4_teacher_opus_pilot runs/phase4_teacher_opus --out artifacts/phase4_teacher_routing_dataset.jsonl`
- `python -m vao.training.build_routing_dataset --runs runs/paper_dev/model_comparison --exclude_holdout --out artifacts/paper_dev_routing_dataset.jsonl`
- `python -m vao.training.train_routing_lora --config configs/phase5_routing_student.yaml`
- `python -m vao.orchestrator --config configs/phase5_routing_student_online.yaml --models local_stub,routing_student --steps 3`
- `python -m vao.analysis.dataset_audit --dataset artifacts/phase4_teacher_routing_dataset.jsonl --json_out artifacts/offline_routing_dataset_audit.json --md_out artifacts/offline_routing_dataset_audit.md`
- `python -m vao.analysis.replay_routing --dataset artifacts/phase4_teacher_routing_dataset.jsonl --student_model training/phase5_routing_student/model.pkl --json_out artifacts/replay_router_comparison.json --md_out artifacts/replay_router_comparison.md`
- `python -m vao.training.offline_routing_experiments --config configs/offline_routing_student.yaml`
- `python -m vao.training.lora_smoke --out artifacts/local_lora_smoke.json --env_out artifacts/local_training_stack_audit.json`
- `python -m vao.training.train_local_lora_router --config configs/offline_lora_router.yaml`
- `python -m vao.orchestrator --config configs/feedback_use_cb.yaml --run-id cb_local_fixed_micro`
- `python -m vao.analysis.run_diagnostics_visuals --run_dir runs/feedback_use_cb/cb_local_fixed_micro --single_mode micro`

The active config catalog is in `configs/README.md`. Retained artifacts are cataloged in `artifacts/README.md` and `artifacts/MANIFEST.json`.

The closed-source and open-weight model adapters share the same batched C(a)
interface as the deterministic `local_stub` backend. Claude aliases use
`ClaudeHaikuAdapter` with API or CLI transport; `qwen_coder_batch_strict`
targets an OpenAI-compatible `/v1/chat/completions` endpoint, such as
vLLM/SGLang or the minimal `scripts/qwen_openai_compat_server.py` smoke server.
Normal tests use fixtures/mocks and do not require live model calls.

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
- Per-run diagnostics plots retained for current runs are under `artifacts/plots/`.
- The artifact catalog is in `artifacts/README.md`; superseded Phase 1/2/3/3.5 and one-off smoke artifacts were removed.
- First paper dev R0 is complete with `gpt-5.3-codex-spark`: 3 dev profiles, 3 steps each, 54 branch evaluations, all runs validated. Aggregate wall-clock was `105.0s/step`; top-1 routing matched a verified-best branch on `2/9` steps; best visible loss was `0.1784` vs best counterfactual loss `0.1087`.
- Qwen smoke is validated through `qwen_coder_batch_strict` with `Qwen/Qwen2.5-Coder-1.5B-Instruct`.
- The historical LangGraph direct-edit backend has been removed from the active code/config/test surface because current comparisons require one shared prompt per step.
- The Haiku-vs-Qwen hard-profile comparison now has three validated 10-step repeats per backend. Aggregate R0-R2: Haiku batch took `251.4s/step`, `$5.626` total, routing accuracy `5/30`, branch correctness `0.67`, best visible loss `0.1652`, and best counterfactual loss `0.1010`. Qwen direct took `188.4s/step`, local serving cost `$0`, routing accuracy `4/30`, branch correctness `1.00`, best visible loss `0.9708`, and best counterfactual loss `0.9690`. Qwen is safer and faster in this setup but conservative; Haiku finds much stronger edits but has more invalid/incorrect branches.
- The Haiku-vs-Qwen hard-profile comparison now also has an R0-R4 aggregate with five validated 10-step repeats per backend. Haiku batch: `242.1s/step`, `$9.165` total, routing `10/50`, mean routing regret `0.5583`, branch correctness `0.61`, best visible loss `0.1107`, best counterfactual loss `0.1010`. Qwen direct: `203.9s/step`, local serving cost `$0`, routing `12/50`, mean routing regret `0.0114`, branch correctness `1.00`, best visible loss `0.9708`, best counterfactual loss `0.9690`. R0-R4 artifacts are under `artifacts/haiku_vs_qwen_10step_r0_r4_*`.
- Post R0-R4 hardening added a fast candidate preflight before full benchmark evaluation. Replay on historical Haiku branches suggests it catches 99/118 invalid branches with zero false rejects. Failure analysis artifacts are under `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.*`.
- Prompt-control hardening now leaves only `src/vao/prompts/single_step_program.txt` as the active model prompt. `preflight` remains verifier-side and identical for all candidates; it is not a model prompt. The prompt-controlled Haiku/Qwen/GPT configs enforce one batched generation prompt per step and no fallback to six per-mode prompts.
- Strict single-prompt smoke results are in `artifacts/single_prompt_smoke_readout.*`. Haiku passed one step with six valid branches. Cached local `Qwen/Qwen3-0.6B-Base` reached the single batch prompt but failed JSON parsing without fallback. Local `Qwen/Qwen2.5-Coder-1.5B-Instruct` on MPS passed after the batch prompt was hardened with an explicit `candidates` object skeleton.
- GPT/Codex backends are implemented through both OpenAI Responses and the local Codex CLI. The active matrix aliases use `codex_cli` because this machine has Codex CLI auth but no exported `OPENAI_API_KEY`. Validated one-step C(a) smokes now exist for `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, and `gpt-5.3-codex-spark`; `gpt-5.2-codex` is not supported by the current Codex ChatGPT account.
- The shared single-prompt matrix config is `configs/hard_single_prompt_model_matrix.yaml`; it includes GPT/Codex, Qwen Coder, Haiku, Sonnet, and Opus 4.6 aliases.
- Offline student eval on the tiny split improved regret/JSD versus the original teacher route on that split, but the online local controlled experiment was worse than the local-stub router. Treat Phase 5 as infrastructure plus a negative first result, not as evidence of a useful student yet.
