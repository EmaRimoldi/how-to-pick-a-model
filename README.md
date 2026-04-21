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

The closed-source and open-weight model adapters are scaffolded behind the same interface as the deterministic `local_stub` backend. `claude_haiku` is the first real backend. It can use `ANTHROPIC_API_KEY` through the Messages API or the authenticated Claude CLI transport when available. Normal tests use fixtures and do not require live model calls.
