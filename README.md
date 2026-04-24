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
- Run logs, artifacts, and generated summaries are cleaned from the repository after use.
- First paper dev R0 is complete with `gpt-5.3-codex-spark`: 3 dev profiles, 3 steps each, 54 branch evaluations, all runs validated.
- Qwen smoke is validated through `qwen_coder_batch_strict` with `Qwen/Qwen2.5-Coder-1.5B-Instruct`.
- Prompt-control hardening leaves a single active prompt and a single batched generation path across the active comparison surface.
