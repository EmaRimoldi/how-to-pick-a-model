# Verifiable Agentic Optimization for Query-Engine Editing

This repository contains the benchmark harness and analysis code for verifiable
agentic optimization on `CandidateQueryEngine`.

The canonical task is iterative editing of `solution.py`. At each step the
model emits a probability distribution over six optimization modes plus one
candidate edit per mode:

- `layout`
- `indexing`
- `topk`
- `caching`
- `summaries`
- `micro`

All six branches are evaluated offline by the verifier. In the default
`top1_only` regime, only the branch selected by the model's top-probability mode
is promoted to the next online state; the remaining counterfactual branches stay
available for protocol analysis.

## Quick Start

Run the deterministic local smoke:

```bash
PYTHONPATH=src:. python -m vao.orchestrator --config configs/hard_local_smoke.yaml --run-id hard_local_smoke
PYTHONPATH=src:. python -m vao.validate_run --run_dir runs/hard_profile/local_smoke/hard_local_smoke
PYTHONPATH=src:. python -m vao.analysis.compute_estimators --runs runs/hard_profile/local_smoke/hard_local_smoke --out artifacts/hard_local_smoke_estimators.csv
pytest -q
```

Or use the helper script:

```bash
scripts/run_hard_profile_smoke.sh
```

To add the one-step Haiku smoke:

```bash
RUN_HAIKU=1 scripts/run_hard_profile_smoke.sh
```

To validate the paper dev/holdout split without live model calls:

```bash
scripts/run_paper_profile_validation.sh
```

Every run writes a self-contained directory with `run_manifest.json`,
`baseline_verification.json`, `evaluations.jsonl`, `run_summary.json`, resolved
config, step branch workspaces, verifier outputs, and prompt snapshots.

## Active Benchmark Profiles

The active split is defined in `configs/profiles.yaml` and
`benchmarks/stateful_query_engine/metadata/instance_config.json`.

- Dev: `hard_balanced_dev`, `hard_range_dev`, `hard_churn_dev`
- Holdout: `hard_balanced_holdout`, `hard_range_holdout`, `hard_churn_holdout`
- Smoke: `hard_balanced_dev`
- Legacy: `hard_optimization`

The three task families cover balanced mixed workloads, range/summary-heavy
workloads, and churn/top-k/update-heavy workloads. Holdout instances are
reserved for final generalization checks.

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
- `python -m vao.orchestrator --config configs/feedback_use_cb.yaml --run-id cb_local_fixed_micro`
- `python -m vao.analysis.run_diagnostics_visuals --run_dir runs/feedback_use_cb/cb_local_fixed_micro --single_mode micro`

The active config catalog is in `configs/README.md`. Experimental outputs are
not retained in the repository by default.

## Oracle-Family Validation

The repository now includes a paper-aligned oracle-family validation path that
separates:

- `task modes`: workload families such as `range_local_scans` and `topk_stress`
- `action modes`: the six branch labels used by the inner editing solver

Main commands:

- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_pilot --config configs/oracle_family_pilot.yaml --models gpt_5_3_codex_spark_batch_strict --families range_local_scans,topk_stress --seeds 7301 --split pilot --steps 1 --run-prefix oracle_family_real --output-root runs/oracle_family_real`
- `PYTHONPATH=src:. python -m vao.analysis.task_mode_decomposition --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real --out-dir artifacts/oracle_family_decomposition_rel5 --success-mode relative_improvement --improvement-threshold 0.05 --smaller-model gpt-5.3-codex-spark --larger-model gpt-5.3-codex`
- `PYTHONPATH=src:. python -m vao.analysis.task_mode_threshold_sweep --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real --out-dir artifacts/oracle_family_threshold_sweep --thresholds 0.0,0.05,0.1 --smaller-model gpt-5.3-codex-spark --larger-model gpt-5.3-codex`
- `PYTHONPATH=src:. python -m vao.analysis.task_mode_robustness --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real --out-dir artifacts/oracle_family_robustness_rel5 --success-mode relative_improvement --improvement-threshold 0.05`
- `PYTHONPATH=src:. python -m vao.analysis.task_mode_bootstrap --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real --out-dir artifacts/oracle_family_bootstrap_rel5 --success-mode relative_improvement --improvement-threshold 0.05 --smaller-model gpt-5.3-codex-spark --larger-model gpt-5.3-codex --bootstrap-samples 400 --seed 0`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_campaign_plan --config configs/oracle_family_5model_campaign.yaml --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real runs/oracle_family_5model_smoke --out-dir artifacts/oracle_family_5model_campaign_plan`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_multimodel_visuals --runs runs/oracle_family_real runs/oracle_family_spark_ext runs/oracle_family_codex_real runs/oracle_family_5model_smoke --out-dir artifacts/oracle_family_multimodel_visuals_rel5 --success-mode relative_improvement --improvement-threshold 0.05`

Iterative extension:

- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_latent_modes --out-dir artifacts/oracle_family_latent_mode_selection -k 4`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_pilot --config configs/oracle_family_iterative_multistep.yaml --models gpt_5_3_codex_spark_batch_strict,gpt_5_3_codex_batch_strict --families negative_lookup_churn,topk_stress,temporal_repeat_windows,wide_range_churn --seeds 8101:2 --split pilot --steps 10 --run-prefix oracle_family_iterative --output-root runs/oracle_family_iterative_top1`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_iterative --runs runs/oracle_family_iterative_top1 runs/oracle_family_iterative_parallel --out-dir artifacts/oracle_family_iterative_partial_multimode --taus 0.0,0.05,0.1 --success-kinds terminal,anytime --smaller-model gpt-5.3-codex-spark --larger-model gpt-5.3-codex`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_pilot --config configs/oracle_family_iterative_fixed_mode.yaml --models gpt_5_3_codex_spark_batch_strict --families topk_stress --seeds 9101:1 --split pilot --steps 10 --selection-policy fixed_mode --selected-mode indexing --output-root runs/oracle_family_iterative_fixed_indexing --run-prefix oracle_family_iterative_fixed_indexing`
- `PYTHONPATH=src:. python -m vao.analysis.oracle_family_policy_compare --analysis top1=artifacts/oracle_family_iterative_partial_top1 fixed_indexing=artifacts/oracle_family_iterative_fixed_indexing_partial fixed_topk=artifacts/oracle_family_iterative_fixed_topk_partial --out-dir artifacts/oracle_family_policy_compare_partial_topk --success-kind anytime --tau 0.05`

The iterative path adds three pieces missing from the one-step theorem-facing
analysis:

- horizon selection via a one-standard-error rule on the oracle objective curve
- per-step action-routing diagnostics over the six action modes
- fixed-mode ablations that treat a single action mode as a locked policy

Paper-facing summary:

- `docs/Document_4_Oracle_Family_Empirical_Validation.md`
- `docs/Document_5_Multimodel_Campaign_and_Figures.md`

Paper-facing artifacts use uniform task-mode priors for the main theorem-facing
comparison:

- `artifacts/oracle_family_decomposition_rel5_topup_uniform/`
- `artifacts/oracle_family_bootstrap_rel5_topup_uniform/`
- `artifacts/oracle_family_threshold_sweep_topup_uniform/`
- `artifacts/oracle_family_robustness_rel5_topup_uniformstate/`

## AutoResearch CIFAR-10 Benchmark

The repository now also contains a second benchmark surface under
`benchmarks/autoresearch_cifar10/`. It keeps the same iterative branch protocol
and theorem-facing quantities, but changes the optimized object from a query
engine to a CPU-only CIFAR-10 training script.

Main commands:

- `PYTHONPATH=src:. python -m vao.orchestrator --config configs/autoresearch_cifar10_local_smoke.yaml --steps 1 --run-id autoresearch_cifar10_smoke`
- `PYTHONPATH=src:. python -m vao.analysis.autoresearch_cifar10_mode_catalog --out-dir artifacts/autoresearch_cifar10_mode_catalog`
- `PYTHONPATH=src:. python -m vao.analysis.autoresearch_cifar10_pilot --config configs/autoresearch_cifar10_pilot.yaml --models autoresearch_local_stub --families short_budget_clean,noisy_regularized --seeds 7001 --steps 1 --train-subset-size 512 --val-subset-size 256 --max-train-steps 2 --output-root runs/autoresearch_cifar10/pilot_smoke --run-prefix autoresearch_pilot_smoke`

In this benchmark:

- latent modes are training regimes (`short_budget_clean`, `noisy_regularized`,
  `imbalanced_long_tail`, `schedule_sensitive`)
- the six canonical branch labels are reused as action-mode aliases for
  architecture, optimizer, learning-rate, regularization, schedule, and
  batching edits
- task quality is validation loss (`val_loss` / `val_bpb`)

See `docs/Document_6_AutoResearch_CIFAR10_Task.md` for the benchmark-specific
mapping.

## Prompt Surface

The only active model-generation prompt is
`src/vao/prompts/single_step_program.txt`. Each step asks for `mode_probs`,
`mode_ranking`, and all six branch edits in a single JSON response. The modes
are experimental labels, not edit permissions.

Structured edits are the active edit protocol. The harness applies operations
such as `replace_exact` and `replace_function` to branch-local copies and then
verifies fully materialized `proposed_solution.py` files.

## Qwen Smoke Setup

For an Engaging GPU smoke, the tested path was:

```bash
ssh engaging
salloc -p mit_preemptable -t 01:00:00 -c 8 --mem=32G --gres=gpu:l40s:1
module load miniforge/25.11.0-0 cuda/12.9.1
python -m pip install --user --upgrade 'transformers>=4.46' sentencepiece safetensors
python ~/vao_qwen_smoke/qwen_openai_compat_server.py \
  --model Qwen/Qwen2.5-Coder-1.5B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16
```

Then tunnel `localhost:8000` to the compute node, replacing `node1632` with the
allocated node:

```bash
ssh -N -L 8000:node1632:8000 engaging
```

Run locally:

```bash
RUN_ID=hard_qwen_batch_smoke_1step \
OPENAI_COMPATIBLE_BASE_URL=http://localhost:8000/v1 \
scripts/run_qwen_smoke.sh
```

## Current Status

- The active benchmark surface is benchmark-only.
- C(b) feedback-use infrastructure is available for local or controlled diagnostics via `feedback_condition: cb`, `visibility_regime: all_branches`, and `ask_post_feedback_distribution: true`.
- The `runs/` tree is local `gitignored` workspace state; prune obsolete smoke, topup, and debug runs periodically to keep the checkout small.
- First paper dev R0 is complete with `gpt-5.3-codex-spark`: 3 dev profiles, 3 steps each, 54 branch evaluations, all runs validated.
- Qwen smoke is validated through `qwen_coder_batch_strict` with `Qwen/Qwen2.5-Coder-1.5B-Instruct`.
- Prompt-control hardening leaves a single active prompt and a single batched generation path across the active comparison surface.
