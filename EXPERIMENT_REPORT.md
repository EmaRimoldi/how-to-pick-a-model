# Experiment Report

## Status

The repository now contains a working first-pass framework for the canonical C(a) protocol: one online trajectory, six mode-constrained candidate branches per step, offline verification for all branches, and top-1-only branch promotion.

## Implemented

- Ported stateful query-engine benchmark components into `benchmarks/stateful_query_engine/`.
- Added `src/vao/` package with schemas, taxonomy, classifier, verifier wrapper, branch workspaces, adapters, orchestrator, visibility policies, estimators, analysis scripts, and routing dataset export.
- Added configs, scripts, tests, project log, assumptions, TODO, and README.
- Added deterministic `local_stub` backend for reproducible framework validation without external model access.

## Smoke Run

Command:

```bash
PYTHONPATH=src:. python -m vao.orchestrator --config configs/phase1_dev.yaml --models local_stub --profiles paper_development --steps 2 --run-id smoke_local_stub
```

Results:

- Run directory: `runs/phase1_dev/smoke_local_stub`
- Steps completed: 2
- Branch evaluations: 12
- Branches per step: 6
- Visibility regime: `top1_only`
- Promoted modes: `indexing`, then `caching`
- Baseline loss: `1.0063325319491947`
- Best visible loss: `0.14148213936363915`
- Best counterfactual loss: `0.14148213936363915`

Generated artifacts:

- `artifacts/phase1_dev_estimators.csv`
- `artifacts/baseline_eval.json`
- `artifacts/routing_all.jsonl`
- `artifacts/routing_train.jsonl`
- `artifacts/routing_dev.jsonl`
- `artifacts/tables_endpoint.md`

## Validation

Commands run:

```bash
pytest -q
PYTHONPATH=src:. python -m benchmarks.stateful_query_engine.dynamic_benchmark --solution benchmarks/stateful_query_engine/solution_template.py --profile paper_development --out artifacts/baseline_eval.json
PYTHONPATH=src:. python -m vao.verifier --smoke_test
PYTHONPATH=src:. python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv
PYTHONPATH=src:. python -m vao.training.build_routing_dataset --runs runs/phase1_dev --train_out artifacts/routing_train.jsonl --dev_out artifacts/routing_dev.jsonl --out artifacts/routing_all.jsonl
```

Validation result:

- `pytest -q`: 15 passed.
- Direct dynamic benchmark: baseline solution correct on `paper_development`.
- Verifier smoke: baseline solution correct on `paper_development`.
- Smoke artifact check: every branch contains `parent_solution.py`, `proposed_solution.py`, `patch.diff`, `proposal.json`, and `verification.json`.

## Known Gaps

- Claude Code and OpenAI-compatible adapters are scaffolds that fall back to `local_stub`.
- Shared-checkpoint controlled phi and full C(b) pre/post feedback-use diagnostics are not implemented beyond shared estimator/scaffold functions.
- Routing LoRA training is intentionally scaffolded only; no model training was run.
- The PDFs were not parsed because `pdftotext` is unavailable; the Markdown implementation guide was used as the operational source of truth.

## Phase 2 Protocol Audit Results

Phase 2 did not integrate Claude, Opus, Haiku, Qwen, or any expensive model backend. It focused on validating the C(a) protocol with deterministic local backends.

Audit implementation:

- Added `python -m vao.validate_run --run_dir <RUN_DIR>`.
- Added a leakage-probe backend and pytest case where `caching` is top-1 by model probability while `indexing` is the best verified counterfactual.
- Added explicit `parent_latent_loss` logging to step records.

Audit findings:

- All six candidate branches at each step are generated from the exact same parent solution hash.
- All six branches are evaluated offline.
- Only the top-1 branch according to `mode_probs` is promoted in `top1_only`.
- Non-selected counterfactual results are logged in `evaluations.jsonl` but are excluded from next-step visible branch feedback.
- `selected_as_visible` and `promoted_as_parent` are correctly logged as one branch per step in C(a).
- `candidate_batch_id` groups exactly six candidate proposals per step.
- `mode_probs` include exactly the six canonical modes and sum to 1.
- `declared_mode` and `inferred_mode` are logged separately.
- The audit found and fixed one bug: `parent_latent_loss` was initially logged after promotion. Gain computation already used the pre-promotion parent loss; the logged field now also records the step-start parent loss.

Phase 2 deterministic expansion:

- Profiles: `paper_development`, `memory_development`, `development`
- Repeats per profile: 3
- Steps per run: 5
- Branches per step: 6
- Runs: 9
- Total steps: 45
- Total branch evaluations: 270
- Validator result: all 9 runs passed

Generated Phase 2 artifacts:

- `artifacts/phase2_dev_estimators.csv`
- `artifacts/phase2_routing_dataset.jsonl`
- `artifacts/phase2_summary.json`

Aggregate Phase 2 summary:

- Routing records: 45
- Mean best loss across estimator rows: `0.5315144632525265`
- Mean routing regret: `0.4836351511535289`
- Mean JSD: `0.31462168201836854`
- Invalid branch rate: `0.0`
