# Project Log

## 2026-04-21

### Phase 0: Document and Repository Inspection

- Confirmed the new project directory initially contained only `docs/Document_1_NeurIPS_style_research_paper.pdf`, `docs/Document_2_Implementation_Guide.md`, and `docs/Document_3_Project_Overview.pdf`.
- Read `Document_2_Implementation_Guide.md` and used it as the operational source of truth.
- Attempted PDF extraction with `pdftotext`; the tool is not installed, so the PDFs were not parsed in this work session.
- Inspected the existing read-only implementation under `/Users/emanuelerimoldi/Documents/GitHub/stateful_query_engine`.
- Identified reusable components: solution template, dynamic benchmark, correctness verifier, performance evaluator, scoring, workload generation, reference engine, baseline candidate, safety gate, and prior logging conventions.
- Confirmed `/Users/emanuelerimoldi/Documents/GitHub/NeurIPS_2026` is not currently a Git repository, so phase commits cannot be made.

### Phase 1: Repository Structure

- Created the project layout with `configs/`, `benchmarks/`, `src/vao/`, `scripts/`, `tests/`, `runs/`, and `artifacts/`.
- Added `README.md`, `pyproject.toml`, `requirements.txt`, `.gitignore`, `PROJECT_LOG.md`, `ASSUMPTIONS.md`, and `TODO.md`.
- Confirmed all three research documents already exist under `docs/`.

### Phase 2: Benchmark Porting Started

- Copied the old benchmark source into `benchmarks/stateful_query_engine/`.
- Rewrote imports from `stateful_query_engine.*` to `benchmarks.stateful_query_engine.*`.
- Patched the dynamic benchmark root path for the new location and added `--solution` as an alias for `--candidate-file`.
- Patched the dynamic benchmark CLI to accept the guide's `--out` form and default `run_id` from the output filename.

### Phase 3: Canonical Protocol

- Implemented `vao.orchestrator` with the C(a) six-branch loop.
- Added isolated branch workspaces under `runs/<run_id>/steps/step_XXXX/branches/<mode>/`.
- Added deterministic `local_stub` agent backend plus Claude Code and OpenAI-compatible adapter scaffolds.
- Implemented top-1-only promotion while preserving all offline counterfactual branch evaluations.

### Phase 4: Logging and Mode Classification

- Implemented Pydantic schemas for mode distributions, proposals, branch evaluations, step records, run manifests, and routing records.
- Implemented `classify_edit_mode(pre_source, post_source)` with evidence for layout, indexing, topk, caching, summaries, and micro.
- Logged declared and inferred modes, candidate source hashes, validation failures, raw verifier paths, gains, branch visibility, and promotion flags.

### Phase 5: Estimators

- Implemented verified gain, productive-mode proxy, routing regret, JSD, runtime mode-conditioned phi, endpoint best loss, success threshold, cost summary, and feedback alignment gain.
- Added `vao.analysis.compute_estimators` and `vao.analysis.make_tables`.
- Fixed table generation to avoid an undeclared optional `tabulate` dependency.

### Phase 6: Routing Dataset Builder

- Implemented `vao.training.build_routing_dataset`.
- Added scaffold entrypoints for later routing LoRA training and post-trained student evaluation.

### Phase 7: Tests and Smoke Experiment

- Ran `pytest -q`: 15 tests passed.
- Ran `PYTHONPATH=src:. python -m vao.verifier --smoke_test`: baseline verified correct on `paper_development`, latent loss `1.0026940572007794`.
- Ran the guide-style direct dynamic benchmark command and wrote `artifacts/baseline_eval.json`; baseline verified correct with latent loss `1.000728373210718`.
- Ran `PYTHONPATH=src:. python -m vao.orchestrator --config configs/phase1_dev.yaml --models local_stub --profiles paper_development --steps 2 --run-id smoke_local_stub`.
- Smoke run output: `runs/phase1_dev/smoke_local_stub`.
- Smoke run completed 2 steps, 12 branch evaluations, 6 candidates per step, top-1 promotions `indexing` then `caching`.
- Smoke best visible loss: `0.14148213936363915`; best counterfactual loss: `0.14148213936363915`.
- Generated `artifacts/phase1_dev_estimators.csv`, `artifacts/routing_all.jsonl`, `artifacts/routing_train.jsonl`, `artifacts/routing_dev.jsonl`, and `artifacts/tables_endpoint.md`.
