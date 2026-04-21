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

## Phase 3 Real Backend Results

Phase 3 integrated the first real LLM backend and ran only small controlled Haiku experiments. Opus, Qwen, and post-training were not run.

Backend implementation:

- Added `ClaudeHaikuAdapter` with strict output parsing and validation.
- Added prompt templates in `src/vao/prompts/`.
- Added deterministic JSON repair for mode distributions and one model-reprompt repair path for invalid JSON/code.
- Added fixture-based parser/prompt tests so normal `pytest` does not require live Claude calls.
- The local environment had no `ANTHROPIC_API_KEY` and no installed `anthropic` package. It did have an authenticated Claude CLI, so live runs used Claude CLI transport with `--model haiku`, structured output schemas, disabled tools, and per-call budget caps.

Live runs:

- Smoke: `runs/phase3_real_backend/haiku_smoke/haiku_smoke`
- Dev: `runs/phase3_real_backend/haiku_dev/haiku_dev_paper_development`
- Dev: `runs/phase3_real_backend/haiku_dev/haiku_dev_memory_development`
- Dev: `runs/phase3_real_backend/haiku_dev/haiku_dev_development`

Totals:

- Runs: 4
- Steps: 11
- Branch evaluations: 66
- Routing dataset records: 11
- All Phase 3 runs passed `vao.validate_run`.
- Logged Claude CLI cost estimate: about `$5.18` total, averaging `0.4711532409090909` USD per step.
- Average wall-clock time: `337.27964359521866` seconds per step.

Artifacts:

- `artifacts/phase3_haiku_estimators.csv`
- `artifacts/phase3_haiku_routing_dataset.jsonl`
- `artifacts/phase3_haiku_summary.json`
- `artifacts/phase3_haiku_failure_modes.json`

Protocol behavior:

- Haiku followed the protocol shape: six branches per step, valid mode distributions, top-1 promotion, and no leakage of non-selected branch feedback into next-step visible history.
- `mode_probs` were meaningful rather than uniform-only or single-mode degenerate. Haiku selected mostly `indexing` and `topk` in these small runs.
- Generated edits were diverse across declared modes.
- Declared/inferred agreement was mixed:
  - `layout`: `1.0`
  - `indexing`: `0.09090909090909091`
  - `topk`: `0.9090909090909091`
  - `caching`: `1.0`
  - `summaries`: `0.9090909090909091`
  - `micro`: `0.0`
- Counterfactual branches revealed routing mistakes. Mean routing regret was `1.179063963942385`, compared with Phase 2 local-stub mean routing regret `0.4836351511535289`.
- Mean JSD was `0.4415179926671302`, compared with Phase 2 local-stub mean JSD `0.31462168201836854`.

Correctness and failures:

- Correctness by declared mode:
  - `layout`: `1.0`
  - `indexing`: `0.9090909090909091`
  - `topk`: `0.8181818181818182`
  - `caching`: `1.0`
  - `summaries`: `1.0`
  - `micro`: `0.9090909090909091`
- Parse/repair failure rate: `0.015151515151515152`
- Code validation failure rate: `0.015151515151515152`
- Verifier runtime failure rate: `0.015151515151515152`
- One unsafe candidate used a banned `.remove()` attribute call during initial generation; the repair prompt produced a safe candidate.
- One indexing branch failed at verifier runtime due to invalid `bisect_left` tuple/key comparison.

Readiness for Opus:

The protocol and logging pipeline are ready for a small Opus teacher pilot. Before spending Opus budget, the Haiku run suggests adding stricter pre-verifier dynamic smoke checks for candidate constructors and common operations, and improving prompts for `indexing` and `micro` so declared mode better matches inferred behavior.

## Patch-Based Edit Protocol Update

After reviewing the Phase 3 timing and token profile, the Claude Haiku candidate contract was changed from full-file replacement to patch-based editing.

Current behavior for future Claude runs:

- The parent `solution.py` is still duplicated into six independent branch workspaces, one per mode.
- Claude now returns a structured `unified_diff`, not a complete `solution.py`.
- The framework saves the model's patch as `model_edit.diff`.
- The framework applies the patch to the branch-local parent copy and materializes `proposed_solution.py` only for validation and verifier import.
- All six branches still share the same parent hash, are evaluated offline, and only the top-1 branch by `mode_probs` is promoted.

Validation after the change:

- `pytest -q`: 27 passed.
- `PYTHONPATH=src:. python -m vao.verifier --smoke_test`: passed.
- `PYTHONPATH=src:. python -m vao.validate_run --run_dir runs/phase1_dev/patch_protocol_local_smoke`: passed with 1 step and 6 branches.

The existing Phase 3 Haiku artifacts were produced before this patch-based contract change and should be interpreted as full-file replacement runs. New Claude runs will use patch-based candidate edits.
