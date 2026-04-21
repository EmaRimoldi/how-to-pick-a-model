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

### Phase 4 Teacher Experiments

- Added `configs/phase4_teacher_opus_pilot.yaml` and `configs/phase4_teacher_opus.yaml` using the frozen replacement-file C(a) protocol.
- Verified the local Claude CLI can invoke Opus, mapped by the CLI to `claude-opus-4-6`.
- Ran the Opus teacher pilot across `paper_development`, `memory_development`, and `development`: 3 validated runs, 9 steps, 54 branch evaluations.
- Pilot validation passed: `pytest -q` passed with 33 tests before routing-student additions; `PYTHONPATH=src:. python -m vao.verifier --smoke_test` passed; `vao.validate_run` passed on all pilot run directories.
- Generated `artifacts/phase4_teacher_pilot_summary.json`, `artifacts/phase4_teacher_pilot_estimators.csv`, `artifacts/phase4_teacher_pilot_failure_modes.json`, and `artifacts/phase4_teacher_pilot_routing_dataset.jsonl`.
- Attempted production Opus collection under `runs/phase4_teacher_opus/` with target matrix 3 profiles x 3 repeats x 5 steps.
- The first production run `runs/phase4_teacher_opus/opus_teacher_dev_r0` completed 3 valid steps and 18 branch evaluations before `claude_cli_failed:1` stopped the next distribution call.
- The partial production run passed `vao.validate_run`, so its completed steps were retained as valid teacher data.
- Combined validated teacher data now contains 4 runs, 12 steps, and 72 branch evaluations.
- Generated `artifacts/phase4_teacher_dev_summary.json`, `artifacts/phase4_teacher_dev_estimators.csv`, `artifacts/phase4_teacher_routing_dataset.jsonl`, and `artifacts/phase4_teacher_run_index.json`.

### Phase 5 Routing-Only Post-Training

- Added a routing-only training pipeline in `src/vao/training/train_routing_lora.py`.
- Because `peft` and `trl` are not installed locally, the first student uses a deterministic TF-IDF plus logistic-regression router and records `lora_used: false`.
- Added `src/vao/agents/routing_student_adapter.py`, which uses the trained router for `mode_probs` and deterministic local-stub candidate edits for online routing-only evaluation.
- Added `configs/phase5_routing_student.yaml` and `configs/phase5_routing_student_online.yaml`.
- Trained on `artifacts/phase4_teacher_routing_dataset.jsonl`: 12 records total, 9 train, 3 eval.
- Offline eval: top-1 accuracy `0.3333333333333333`; predicted top-1 regret `0.3552415586184802` vs original top-1 regret `1.8929338747685003` on the tiny eval split; predicted JSD `0.4982921482896754` vs original JSD `0.6960718717431963`.
- Ran online local controlled evaluation with 6 validated runs: 3 local-stub baseline runs and 3 routing-student runs.
- Online result was negative: routing student mean routing regret `0.9519646135760867` vs local-stub `0.41225891166210665`; student best loss was worse by `0.3680211883269071`.
- Final validation passed: `pytest -q` passed with 34 tests; verifier smoke passed; `vao.validate_run` passed on all Phase 4 and Phase 5 run directories used for artifacts.

### Offline Progress During Claude Quota Pause

- Claude quota became unavailable, so all subsequent work avoided Claude CLI, Anthropic API, Opus, Haiku, Qwen, and any new teacher generation.
- Added `src/vao/analysis/dataset_audit.py` and generated `artifacts/offline_routing_dataset_audit.json` plus `.md`.
- The existing teacher routing dataset contains 12 examples: `paper_development` 6, `development` 3, and `memory_development` 3.
- Productive-mode labels are highly imbalanced: `layout` 6, `indexing` 3, `micro` 2, `caching` 1, with no `topk` or `summaries` positives.
- Original teacher routing regret is positive on 8 of 12 examples, with mean `0.9385370051379591` and max `4.217488474179428`.
- Added `src/vao/analysis/replay_routing.py` for one-step logged-counterfactual replay and generated `artifacts/replay_router_comparison.json` plus `.md`.
- Replay comparison shows `saved_routing_student` has the lowest top-1 regret among nontrivial logged policies (`0.19060538911168567`), while `always_layout` has the lowest expected regret (`0.3347770188314449`) because of label imbalance.
- Added stronger offline classical routing experiments in `src/vao/training/offline_routing_experiments.py`, profile/history/source features in `src/vao/training/routing_features.py`, and config `configs/offline_routing_student.yaml`.
- Selected offline classical model: `tfidf_word_multinomial_nb` by leave-one-out expected regret. Generated `artifacts/offline_routing_train_summary.json`, `artifacts/offline_routing_eval_summary.json`, `artifacts/offline_routing_model_comparison.json`, and `artifacts/offline_router_leaderboard.*`.
- Installed and validated local training dependencies with `python -m pip install peft trl`; recorded versions in `artifacts/local_training_stack_audit.json`.
- Added `src/vao/training/lora_smoke.py`; the toy PEFT LoRA smoke test passed without model downloads.
- Added `src/vao/training/train_local_lora_router.py` and `configs/offline_lora_router.yaml`; trained a cached `distilbert-base-uncased` LoRA router locally on existing teacher data only.
- Local LoRA router training loss decreased from `1.7637574672698975` to `0.5818454623222351`, but eval still predicted only `layout` and did not beat classical/replay baselines.
- Generated `artifacts/routing_failure_analysis.md`, `artifacts/routing_confusion_analysis.json`, `artifacts/replay_online_like_summary.*`, and `artifacts/future_teacher_scaling_plan.md`.

### Routing Choice Visualization

- Added `src/vao/analysis/routing_choice_visuals.py` to summarize how often a router's top-probability mode matches the verified-best branch at each checkpoint.
- Generated `artifacts/routing_choice_summary.json` and `artifacts/routing_choice_visuals.md`.
- Generated visualizations under `artifacts/plots/` for dataset-level accuracy, Phase 4 Opus correct/incorrect counts, selected-vs-best mode counts, confusion matrix, and per-step routing regret.
- Phase 4 Opus teacher result by verified-best branch: 4 correct choices and 8 incorrect choices across 12 validated teacher steps.

### C(b) Feedback-Use Infrastructure

- Added optional C(b) protocol support to `vao.orchestrator`: `feedback_condition: cb`, `visibility_regime: all_branches`, and `ask_post_feedback_distribution: true`.
- Added controlled promotion through `selection_policy: top1`, `fixed_mode`, or `mode_sequence`. Non-top1 controlled runs preserve `selected_mode_top1` as the model argmax and log the actual promoted branch in `selected_mode`.
- Each C(b) step can now log `post_feedback_mode_probs`, `post_feedback_mode_ranking`, raw/parsed post-feedback model output, `feedback_regret_improvement`, and `feedback_jsd_improvement`.
- Updated `vao.validate_run` so C(a) top-1 invariants remain strict while controlled-selection C(b) runs validate the explicitly selected promoted mode.
- Updated `configs/feedback_use_cb.yaml` and ran a local C(b) smoke: `runs/feedback_use_cb/cb_local_fixed_micro`, 2 steps, 12 branch evaluations, validation passed.
- Added `src/vao/analysis/run_diagnostics_visuals.py` and generated per-run plots for the local C(b) smoke plus all validated Phase 4 Opus teacher runs.

### Structured Edit Protocol Debug

- Audited existing replacement vs unified-diff logs with `src/vao/analysis/edit_protocol_debug.py`.
- Observed replacement outputs were about `3706` to `3738` raw chars per candidate on Phase 3/4 runs; unified diff reduced raw output to about `2958` chars but had many apply/repair failures.
- A compact structured one-line edit example is `219` chars and a structured single-function replacement example is `533` chars, compared with `2496` chars for a full template replacement payload.
- Added `src/vao/structured_edits.py` with exact `replace_exact`, `delete_exact`, `insert_before`, `insert_after`, and `replace_function` operations.
- Added parser/prompt support for `edit_format: "structured_edits"` and made it the default future edit protocol for `claude_haiku` and `claude_opus_teacher`.
- Kept `claude_haiku_diff_legacy` and `claude_opus_teacher_replacement_legacy` model configs for fallback comparisons.
- Generated `artifacts/edit_protocol_debug_report.json` and `artifacts/edit_protocol_debug_report.md`.

### Haiku Batch Speed Check

- Added `candidate_generation: batched` support in `vao.orchestrator`.
- Added `ClaudeHaikuAdapter.propose_step_batch`, which asks Haiku for `mode_probs`, `mode_ranking`, and all six structured-edit candidates in one Claude call.
- Added local-stub batch support and regression tests proving the six-branch C(a) contract still holds.
- Added `src/vao/prompts/step_batch_structured.txt`, `configs/phase3_haiku_structured_batch_smoke.yaml`, and `claude_haiku_batch`.
- Ran live Haiku batch smoke: `runs/phase3_real_backend/haiku_structured_batch_smoke/haiku_structured_batch_speed`, 1 step, 6 branches, `vao.validate_run` passed.
- Measured Haiku batch smoke at `132.72114205360413` seconds/step and `$0.17853760000000002` per step.
- Comparison: Haiku structured per-mode smoke was `480.42223167419434` seconds/step and `$0.62889475`; historical Haiku replacement smoke was `326.4316976070404` seconds/step and about `$0.4786131`.
- The speedup came from avoiding six serial candidate-generation calls and repeating the parent/context six times, not merely from shorter candidate text.
- Caveat: one batched `indexing` candidate was rejected by source safety validation and logged as an explicit no-op; batch prompting/repair should be tightened before scaling.
- Generated `artifacts/haiku_batch_speed_debug_report.json` and `artifacts/haiku_batch_speed_debug_report.md`.
- Validation after the speed check: `pytest -q` passed with 47 tests; `PYTHONPATH=src:. python -m vao.verifier --smoke_test` passed; `vao.validate_run` passed on the batch smoke.

### Anti-Leakage Context Recheck

- Rechecked C(a) next-step visibility after adding batched Haiku generation.
- `build_visible_history(..., "top1_only")` still includes only branches with `selected_as_visible=True`.
- `vao.orchestrator` marks exactly one branch visible/promoted in C(a): the branch selected by `selected_mode`, which defaults to `argmax(mode_probs)`.
- `vao.validate_run` checks that next-step visible history contains only the promoted branch when a `visible_history_snapshot` is logged.
- Tightened `summarize_history_for_prompt` so it no longer includes `best_counterfactual_mode`; this prevents future prompt summaries from accidentally leaking offline verifier winners.

### Single Hard Profile

- Replaced the active benchmark profile set in `benchmarks/stateful_query_engine/metadata/instance_config.json` with one canonical profile: `hard_optimization`.
- Removed active config references to `paper_development`, `memory_development`, `development`, `paper_holdout`, `memory_holdout`, and `search_hard_90min`.
- `hard_optimization` uses all nine workload families with `initial_size=2600`, `key_space=120000`, `trace_length=1200`, `traces_per_family=1`, `repetitions=2`, and `warmup_prefix=120`.
- Updated orchestrator/verifier defaults and experiment configs to use `hard_optimization`.
- Added a regression test asserting that the benchmark metadata contains exactly the `hard_optimization` profile.
- Calibrated verifier smoke on `hard_optimization`: baseline solution passed with latent loss `1.0011415088998392` in `62.90119183299248` seconds.

### Hard Profile Experiment Readiness

- Added `configs/hard_local_smoke.yaml`, `configs/hard_local_dev.yaml`, `configs/hard_haiku_batch_smoke.yaml`, and `configs/hard_haiku_batch_pilot.yaml`.
- Added `scripts/run_hard_profile_smoke.sh` for reproducible local smoke runs, with optional `RUN_HAIKU=1` for the one-step Haiku batch smoke.
- Ran local hard smoke: `runs/phase1_dev/hard_profile_local_smoke`, 1 step, 6 branches, `vao.validate_run` passed.
- Ran local hard dev calibration: `runs/hard_profile/local_dev/hard_local_dev_2step_calibration`, 2 steps, 12 branches, `vao.validate_run` passed.
- Local calibration: baseline about `65s`; post-baseline six-branch step about `78s`; no proposal, validation, or verifier failures.
- Ran Haiku batch hard smoke: `runs/hard_profile/haiku_batch_smoke/hard_haiku_batch_smoke_1step`, 1 step, 6 branches, `vao.validate_run` passed.
- Haiku batch hard smoke: total `346.40069103240967s` including baseline, post-baseline `282.3915177824092s`, cost `$0.17126860000000002`, input tokens `64838`, output tokens `22950`, and zero proposal/verifier failures.
- Generated `artifacts/hard_profile_experiment_readiness.json`, `artifacts/hard_profile_experiment_readiness.md`, local/Haiku estimator CSVs, routing datasets, summaries, failure-mode files, and run diagnostic plots.
