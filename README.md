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

## Main Entry Points

- `python -m vao.orchestrator --config configs/phase1_dev.yaml`
- `python -m vao.verifier --smoke_test`
- `python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv`
- `python -m vao.training.build_routing_dataset --runs runs/phase1_dev --train_out artifacts/routing_train.jsonl --dev_out artifacts/routing_dev.jsonl`

The closed-source and open-weight model adapters are scaffolded behind the same interface as the deterministic `local_stub` backend. The smoke experiment intentionally uses `local_stub` so the framework is reproducible without external model credentials.
