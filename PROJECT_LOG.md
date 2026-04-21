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

### Phase 2: Protocol Audit and Anti-Leakage Validation

- Initialized git and committed the smoke-pass framework as `Initial VAO experimental framework smoke pass`.
- Added explicit `parent_latent_loss` logging to step records.
- Added `python -m vao.validate_run --run_dir <RUN_DIR>` to validate C(a) protocol invariants from `evaluations.jsonl` plus branch artifacts.
- Added `LeakageProbeAdapter`, a deterministic backend that assigns top probability to `caching` while the synthetic best counterfactual branch is `indexing`.
- Added `tests/test_anti_leakage_protocol.py` to prove top-1 promotion follows `mode_probs`, not verifier hindsight, and that non-selected branch feedback is absent from the next visible branch history.
- The new anti-leakage test initially exposed a parent-loss auditability bug: `parent_latent_loss` was being logged after branch promotion. Gain computation itself used the pre-promotion parent loss, but the logged parent-loss field was wrong. Fixed `vao.orchestrator` to snapshot `step_parent_loss` at step start and use it for both gain computation and logging.
- Validated the existing phase1 smoke run with `vao.validate_run`; it passed.

### Phase 2: Small Dev-Profile Expansion

- Added `configs/phase2_dev.yaml` with three dev profiles: `paper_development`, `memory_development`, and `development`.
- Ran deterministic local backend expansion: 3 profiles x 3 repeats x 5 steps x 6 branches.
- Outputs are stored under `runs/phase2_dev/`.
- All 9 phase2 runs passed `vao.validate_run`.
- Total phase2 branch evaluations: 270.
- Generated `artifacts/phase2_dev_estimators.csv` with 9 rows.
- Generated `artifacts/phase2_routing_dataset.jsonl` with 45 routing records.
- Generated `artifacts/phase2_summary.json`.

### Phase 2 Protocol Audit Results

- All six candidate branches at each step are generated from the same parent solution hash.
- All six branches are evaluated offline and have `verification.json` artifacts.
- In `top1_only`, exactly one branch is marked `selected_as_visible` and exactly one branch is marked `promoted_as_parent`.
- The promoted branch matches `argmax(mode_probs)`, not necessarily the best verified counterfactual branch.
- Non-selected counterfactual results remain in the step record but are excluded from reconstructed next-step visible branch history.
- Gains are computed relative to the step-start parent loss and `parent_latent_loss` is now logged consistently.
- Each step has one `candidate_batch_id` grouping exactly six candidate proposals.
- `mode_probs` are validated to include exactly the six canonical modes and sum to 1.
- `declared_mode` and `inferred_mode` are logged separately for each branch.

### Phase 3: Claude Haiku Backend

- Added a strict Claude Haiku backend in `src/vao/agents/anthropic_adapter.py`.
- Added prompt templates under `src/vao/prompts/` for mode distribution, mode-constrained edit generation, JSON repair, and code repair.
- Added parser and validation helpers in `src/vao/agents/claude_parser.py`.
- Added fixture-based parser/prompt tests. Normal pytest does not require live API calls.
- The environment did not have `ANTHROPIC_API_KEY` or the `anthropic` Python package installed, but it did have an authenticated Claude CLI. Phase 3 used Claude CLI transport with `--model haiku`, structured output schema, no tools, and per-call budget caps.
- Added `configs/phase3_haiku_smoke.yaml` and `configs/phase3_haiku_dev.yaml`.
- Ran live Haiku smoke: 1 profile, 2 steps, 12 branches. The run passed `vao.validate_run`.
- Ran live Haiku dev: 3 profiles, 1 run per profile, 3 steps per run, 54 branches. All runs passed `vao.validate_run`.
- Combined Phase 3 totals: 4 runs, 11 steps, 66 branch evaluations.
- Generated `artifacts/phase3_haiku_estimators.csv`, `artifacts/phase3_haiku_routing_dataset.jsonl`, `artifacts/phase3_haiku_summary.json`, and `artifacts/phase3_haiku_failure_modes.json`.
- Total logged Claude CLI cost estimate across Phase 3 live runs: approximately `$5.18`.

### Phase 3 Real Backend Results

- Haiku followed the outer protocol: all runs validated with six branches per step, exactly one top-1 promoted branch, and no counterfactual leakage in visible history.
- `mode_probs` were non-degenerate and changed across steps; selected modes included `indexing` and `topk`.
- Generated edits were diverse across declared modes, but declared/inferred agreement was uneven: strong for `layout`, `caching`, `topk`, and `summaries`, weak for `indexing` and `micro`.
- Counterfactual branches exposed routing mistakes: mean routing regret was `1.179063963942385`, substantially higher than Phase 2 local-stub mean routing regret `0.4836351511535289`.
- Correctness rates by declared mode were: layout `1.0`, indexing `0.9091`, topk `0.8182`, caching `1.0`, summaries `1.0`, micro `0.9091`.
- One candidate required repair after unsafe source validation (`banned attribute call: remove`); repair succeeded.
- One branch caused a verifier runtime failure due to generated code using `bisect_left` with incompatible key/tuple comparison.
- The pipeline is ready for a small Opus teacher pilot from a protocol standpoint, but prompt tuning and stricter pre-verifier dynamic checks are recommended first. Opus was not run in Phase 3.

### Patch-Based Edit Protocol Update

- Replaced the Claude Haiku candidate contract from complete `solution.py` replacement output to structured patch output.
- The Claude edit prompt and JSON schema now require `edit_format: "unified_diff"` and a `unified_diff` from `parent_solution.py` to `proposed_solution.py`.
- Added `src/vao/patches.py` with strict unified-diff application. Context and removed lines must match the branch parent exactly; malformed patches are rejected rather than guessed.
- Updated `ClaudeHaikuAdapter` so each branch starts from the copied parent, saves the model patch as `model_edit.diff`, applies it to materialize `proposed_solution.py`, then lets the existing verifier evaluate that materialized file.
- Added `model_edit_path` to branch evaluation records when a saved model patch exists.
- Kept deterministic local backends working; they may still materialize full candidate files directly for cheap protocol tests.
- Added fixture tests for patch parsing, exact patch application, context mismatch rejection, and prompt rendering that forbids complete replacement-file output.
- Ran `pytest -q`: 27 tests passed.
- Ran `PYTHONPATH=src:. python -m vao.verifier --smoke_test`: passed.
- Ran a 1-step local orchestrator smoke at `runs/phase1_dev/patch_protocol_local_smoke`; `vao.validate_run` passed with 1 step and 6 branch evaluations.

### Phase 3.5 Patch-Based Refactor and Revalidation

- Added protocol-configurable Claude candidate generation: `patch_unified_diff` for patch-faithful experiments and `replacement_file` for production teacher-data generation.
- Added replacement-file prompt/repair templates with explicit `edit_format: "replacement_file"` so production runs are no longer ambiguous.
- Improved unified-diff application to tolerate incorrect hunk line numbers only when the old hunk context matches exactly and uniquely in the branch-local parent.
- Ran patch Haiku smoke V2: `runs/phase35_patch/haiku_smoke/haiku_patch_smoke_v2`, 2 steps, 12 branches, passed `vao.validate_run`.
- Ran patch Haiku dev: 3 profiles x 1 run x 3 steps, 54 branches, all three runs passed `vao.validate_run`.
- Validation after Phase 3.5: `pytest -q` passed with 31 tests; `PYTHONPATH=src:. python -m vao.verifier --smoke_test` passed.
- Generated `artifacts/phase35_patch_summary.json`, `artifacts/phase35_patch_failure_modes.json`, `artifacts/phase35_patch_estimators.csv`, `artifacts/phase35_patch_routing_dataset.jsonl`, and `artifacts/phase35_patch_vs_replacement.json`.

### Production Protocol Decision

- Frozen production protocol for teacher-data generation: C(a) with full replacement-file candidate outputs.
- Rationale: patch-based editing is more faithful to literal edit semantics, but the validated Phase 3.5 dev run was slower and less stable than the Phase 3 replacement-file dev run.
- Dev-to-dev comparison: patch averaged `435.12574399842157` seconds per step vs replacement `340.8956255912781`; patch averaged `$0.5358607722222222` per step vs replacement `$0.46949549444444444`.
- Patch failure rates were also higher: parse/repair/rejection rate `0.18518518518518517`, source validation failure rate `0.12962962962962962`, verifier failure rate `0.18518518518518517`.
- Replacement-file remains the production protocol for Opus teacher data. Patch mode remains available for later method work but will not block teacher/routing-only milestones.
