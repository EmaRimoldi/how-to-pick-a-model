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
- Ran first Haiku batch hard pilot: `runs/hard_profile/haiku_batch_pilot/hard_haiku_batch_pilot_3step`, 3 steps, 18 branches, `vao.validate_run` passed.
- Pilot timing/cost: total `807.0311040878296s`, post-baseline `247.68078547361074s` per step, total cost `$0.60019855`, input tokens `355882`, output tokens `83089`.
- Pilot outcomes: selected modes `layout`, `caching`, `summaries`; best visible loss `0.28242576429393895`; best counterfactual loss `0.2784324758473186`; mean routing regret `0.009569049696577977`.
- Pilot failures: two candidates rejected for banned `list.remove`, one `topk` branch semantically incorrect; verifier infrastructure failures were zero.
- Generated `artifacts/hard_haiku_batch_pilot_*` artifacts and `artifacts/plots/run_hard_haiku_batch_pilot_3step/`.

### Hard Pilot Bugfixes

- Added a narrow deterministic structured-candidate repair for the over-broad `.remove(...)` safety rejection. If the only source-validation error is `banned attribute call: remove`, simple statement-level `container.remove(value)` calls are rewritten to list-comprehension assignments and the repaired source is validated again.
- The repair is logged through `source_repair_status` and `source_repairs` in proposal JSON. The two failed pilot payloads now reparse and validate with `list_remove_rewritten_to_comprehension`.
- Hardened structured-edit prompts for `top_k`: prompts now require exact ordering by value descending and then key ascending, with sorting/heap semantics equivalent to `(-value, key)`.
- No semantic auto-repair was added for wrong `top_k` algorithms; those remain verifier-detected candidate failures because local semantic rewrites would change the model's proposed edit.
- Generated `artifacts/hard_pilot_bugfix_report.json` and `artifacts/hard_pilot_bugfix_report.md`.

### Qwen Open-Weight Smoke

- Implemented a real `OpenAICompatibleAdapter` for `/v1/chat/completions` endpoints. It shares the strict structured-edit parsing, candidate materialization, source validation, and C(a) logging path used by the Claude adapter.
- Set `weak_qwen` to `Qwen/Qwen2.5-Coder-1.5B-Instruct`, a small ungated code model suitable for a first weak-router/editor smoke.
- Added `scripts/qwen_openai_compat_server.py`, a minimal `transformers` OpenAI-compatible server for single-GPU smoke tests when vLLM/SGLang are not installed.
- Added `configs/hard_qwen_batch_smoke.yaml` and `scripts/run_qwen_smoke.sh`.
- Connected to Engaging, allocated one preemptable L40S GPU on `node1632`, installed the minimal user-space serving dependencies, loaded Qwen, and tunneled the endpoint to local `localhost:8000`.
- Added deterministic parser repairs for open-weight output quirks: Python triple-quoted string values inside JSON and unindented `replace_function` method bodies. These repairs are logged in parsed candidate metadata and still require normal source validation.
- Ran adapter-level Qwen probes. The all-in-one batch response was malformed, so the adapter fell back to Qwen distribution plus six Qwen per-mode structured edit calls.
- Ran the full one-step hard-profile Qwen smoke: `runs/hard_profile/qwen_batch_smoke/hard_qwen_batch_smoke_1step`.
- Result: 1 step, 6 branch evaluations, 240.9s total wall-clock, 11,658 input tokens, 1,729 output tokens, no USD cost from local serving, and `vao.validate_run` passed.
- Qwen selected `layout`; the best counterfactual branch was `topk`, so the smoke produced a nonzero routing-regret example while preserving C(a) top-1 visibility.
- Generated `artifacts/hard_qwen_batch_smoke_summary.json`, `artifacts/hard_qwen_batch_smoke_summary.md`, `artifacts/hard_qwen_batch_smoke_estimators.csv`, `artifacts/hard_qwen_batch_smoke_routing_dataset.jsonl`, and plots under `artifacts/plots/run_hard_qwen_batch_smoke_1step/`.
- Validation after changes: `pytest -q` passed with 53 tests; `PYTHONPATH=src:. python -m vao.verifier --smoke_test` passed; `vao.validate_run` passed on the Qwen smoke.

### LangGraph Direct-File Editing

- Added `langgraph>=1.1.9` as a project dependency.
- Added `src/vao/agents/direct_file_edit.py`, a LangGraph loop with restricted branch-local file tools: `read_file`, `replace_exact`, `delete_exact`, `insert_before`, `insert_after`, `replace_function`, `validate_file`, and `finish`.
- Added `src/vao/agents/openai_direct_edit_adapter.py` and registered it as `openai_compatible_direct_edit` in the orchestrator.
- Added `weak_qwen_direct` to `configs/models.yaml`, plus `configs/hard_qwen_direct_edit_smoke.yaml` and `scripts/run_qwen_direct_edit_smoke.sh`.
- Direct-file editing writes immediately to the branch-local `proposed_solution.py`; it does not give Qwen shell access or access to other branches.
- Normal C(a) evaluation is unchanged after the edit loop: the orchestrator diffs parent vs proposed, validates source, infers mode, evaluates all six branches offline, and promotes only the selected branch.
- Added `tests/test_direct_file_edit.py` covering LangGraph tool execution and the direct-edit adapter without live model calls.
- Validation after changes: `pytest -q` passed with 55 tests; `PYTHONPATH=src:. python -m vao.verifier --smoke_test` passed.

### Haiku vs Qwen Hard-Profile R0

- Ran the first matched 10-step hard-profile comparison after validating Qwen direct-file editing.
- Haiku run: `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r0`, using `claude_haiku_batch`, C(a), batched structured edits, 10 steps, and 60 branch evaluations.
- Qwen run: `runs/hard_profile/haiku_vs_qwen/qwen_direct/hard_qwen_direct_10step_r0`, using `weak_qwen_direct`, C(a), LangGraph direct branch-local file editing, 10 steps, and 60 branch evaluations.
- Both runs passed `vao.validate_run`, preserving six branches per step, same parent hash per step, top-1 promotion, and no counterfactual leakage into visible history.
- Haiku aggregate: `302.7s/step`, total cost `$1.940`, routing accuracy `0.20`, mean routing regret `0.4085`, branch correctness `0.83`, best visible loss `0.1860`, best counterfactual loss `0.1090`.
- Qwen direct aggregate: `181.0s/step`, local serving cost `$0`, routing accuracy `0.20`, mean routing regret `0.0140`, branch correctness `1.00`, best visible loss `0.9708`, best counterfactual loss `0.9690`.
- Interpretation: Qwen direct was faster and safer on this run, but mostly selected `layout` and found only small improvements. Haiku explored more modes and found much lower counterfactual losses, but two selected visible branches were incorrect and the run became unstable late.
- Generated combined artifacts: `artifacts/haiku_vs_qwen_10step_r0_summary.*`, `artifacts/haiku_vs_qwen_10step_r0_estimators.csv`, `artifacts/haiku_vs_qwen_10step_r0_routing_dataset.jsonl`, and diagnostic plots under `artifacts/plots/run_hard_haiku_batch_10step_r0/` and `artifacts/plots/run_hard_qwen_direct_10step_r0/`.
- Stopped the Qwen server and released the Engaging GPU allocation after the run completed.

### Haiku vs Qwen Hard-Profile R0-R2

- Ran two additional 10-step repeats for both Haiku batch and Qwen direct, producing three validated repeats per backend.
- Validated runs:
  - `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r0`
  - `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r1`
  - `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r2`
  - `runs/hard_profile/haiku_vs_qwen/qwen_direct/hard_qwen_direct_10step_r0`
  - `runs/hard_profile/haiku_vs_qwen/qwen_direct/hard_qwen_direct_10step_r1`
  - `runs/hard_profile/haiku_vs_qwen/qwen_direct/hard_qwen_direct_10step_r2`
- Total validated matrix: 6 runs, 60 steps, and 360 branch evaluations.
- Haiku aggregate R0-R2: `251.4s/step`, `$5.626` total cost, routing `5/30`, branch correctness `0.67`, selected-branch correctness `0.63`, best visible loss `0.1652`, best counterfactual loss `0.1010`.
- Qwen direct aggregate R0-R2: `188.4s/step`, local serving cost `$0`, routing `4/30`, branch correctness `1.00`, selected-branch correctness `1.00`, best visible loss `0.9708`, best counterfactual loss `0.9690`.
- Interpretation: Qwen direct is faster and much safer but conservative; Haiku produces better optimization opportunities and lower losses but has substantially more candidate failures.
- Generated `artifacts/haiku_vs_qwen_10step_r0_r2_summary.*`, `artifacts/haiku_vs_qwen_10step_r0_r2_estimators.csv`, `artifacts/haiku_vs_qwen_10step_r0_r2_routing_dataset.jsonl`, and diagnostic plots for R1/R2.

### Haiku vs Qwen Hard-Profile R0-R4

- Ran two further 10-step repeats per backend and aggregated five validated repeats per backend.
- Included Haiku runs: R0, R1, R2, R3 retry2, and R4 retry1. Excluded partial Haiku trials `hard_haiku_batch_10step_r3`, `hard_haiku_batch_10step_r3_retry1`, and `hard_haiku_batch_10step_r4` because the Claude CLI exited with code 1 before completing 10 validated steps.
- Included Qwen direct runs: R0, R1, R2, R3, and R4.
- Final validated matrix: 10 runs, 100 steps, and 600 branch evaluations.
- Haiku batch aggregate R0-R4: `242.1s/step`, `$9.165` total cost, routing `10/50`, mean routing regret `0.5583`, branch correctness `0.61`, selected-branch correctness `0.56`, best visible loss `0.1107`, and best counterfactual loss `0.1010`.
- Qwen direct aggregate R0-R4: `203.9s/step`, local serving cost `$0`, routing `12/50`, mean routing regret `0.0114`, branch correctness `1.00`, selected-branch correctness `1.00`, best visible loss `0.9708`, and best counterfactual loss `0.9690`.
- Interpretation: Qwen remains the safer and cheaper weak baseline but makes small improvements. Haiku remains the better optimizer on best visible/counterfactual loss, but produces many more failed or slow candidates and has lower selected-branch correctness.
- Generated `artifacts/haiku_vs_qwen_10step_r0_r4_summary.*`, `artifacts/haiku_vs_qwen_10step_r0_r4_estimators.csv`, combined and per-backend routing datasets, loss-based aggregate visualizations, and diagnostic plots for the new R3/R4 runs.

### R0-R4 Failure Analysis and Preflight Hardening

- Audited the R0-R4 branch tensor before launching more expensive runs.
- Haiku failure pattern: 118/300 branches were incorrect or non-finite, spread across all six modes. Common failures were state-layout inconsistencies, import/runtime errors, aggregate_count divergences, and top_k ordering divergences.
- Qwen failure pattern: 300/300 branches were verifier-correct, but the router selected `layout` 47/50 times while verified-best modes were distributed across all six modes.
- Added `src/vao/candidate_preflight.py`, a deterministic subprocess preflight for generated candidates. It checks constructor, get, put, delete, range_sum, aggregate_count, inclusive bounds, and top_k value-desc/key-asc ordering against the trusted reference engine.
- Integrated preflight into `vao.verifier.evaluate_solution`. A branch that fails preflight is logged as `preflight_failed:*` with `latent_loss=inf` and does not spend the full benchmark verifier budget.
- Historical replay on Haiku R0-R4: preflight would catch 99/118 invalid Haiku branches (`0.839`) with zero false rejects among 182 correct branches.
- Hardened structured-edit and direct-file-edit prompts against mixed storage representations, broken aggregate_count semantics, and layout-default routing. Prompt now explicitly discourages assigning `layout` high probability by default.
- Generated `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.json` and `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.md`.

### Prompt-Control Hardening

- Clarified that candidate preflight is verifier-side only; it does not alter the model prompt and is applied uniformly to all materialized candidates.
- Found that the R0-R4 Haiku/Qwen matrix was not prompt-identical: Haiku used batched structured-edit generation, while Qwen direct used a distribution call plus LangGraph branch-local editing tools.
- Added `src/vao/prompts/shared_canonical_task.txt` and wired it into routing, structured-edit, batched structured-edit, legacy diff/replacement prompts, and Qwen direct-file editing.
- The shared block fixes task-level parity across real backends: same six modes, same CandidateQueryEngine API, same anti-leakage visibility rule, same safety constraints, same top_k/aggregate_count semantics, and same routing guidance.
- Backend-specific wrappers remain explicit: structured/batched backends return JSON edits, while direct-file editing returns restricted tool calls. These wrapper differences are documented as transport/protocol differences, not task differences.
- Added paired prompt-controlled 10-step configs for a future pure ablation: `configs/hard_haiku_prompt_controlled_10step.yaml` and `configs/hard_qwen_prompt_controlled_10step.yaml`.
- Corrected the prompt-controlled configs to use `candidate_generation: batched`: one model-generation prompt per step returns `mode_probs`, `mode_ranking`, and one structured edit for each of the six modes. The framework then applies those six edits to six isolated branch copies.
- Added strict batch model aliases `claude_haiku_batch_strict` and `weak_qwen_batch_strict`. Strict mode disables batch repair and Qwen per-mode fallback so a prompt-controlled run cannot silently become seven prompts.
- Ran a one-step Haiku single-prompt strict smoke: `runs/hard_profile/single_prompt/haiku_batch_structured/hard_haiku_single_prompt_smoke_1step_r0`. It passed `vao.validate_run` with 1 step and 6 branch evaluations.
- Haiku smoke result: 520.3s wall-clock, `$0.2166`, 6/6 branch correctness, selected `layout`, best counterfactual `indexing`, visible selected loss `0.1617`, best counterfactual loss `0.1218`.
- Local Qwen endpoint for the prior Engaging 1.5B Coder run was unavailable. Non-interactive SSH to Engaging failed, so I tested a cached local `Qwen/Qwen3-0.6B-Base` through the same strict single-prompt batch path.
- The cached local Qwen run completed baseline verification but failed the single batch JSON contract with `ModelOutputError: Extra data`. It did not fall back to per-mode prompts and produced zero branch evaluations, which is the correct strict-protocol behavior for malformed batch output.
- Added `artifacts/single_prompt_smoke_readout.json` and `artifacts/single_prompt_smoke_readout.md`.
- Downloaded and served `Qwen/Qwen2.5-Coder-1.5B-Instruct` locally through the OpenAI-compatible smoke server on MPS because Engaging SSH was not available non-interactively.
- First Qwen Coder strict attempt reached the model but failed with `batch_candidates_missing_or_not_object`: the model returned `candidates` as a list of method edits instead of an object keyed by mode.
- Hardened the single batch prompt with an explicit JSON skeleton and an instruction that `candidates` must be an object with exactly the six mode keys, not a list.
- Re-ran Qwen Coder strict single-prompt smoke successfully: `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_coder_single_prompt_smoke_1step_r1_promptfix` passed `vao.validate_run` with 1 step, 6 branch evaluations, 6/6 branch correctness, 377.7s wall-clock, and local `$0` API cost.
- Qwen Coder selected `caching` with probability 1.0; best counterfactual mode was `micro`, so the smoke produced a routing-regret example while preserving C(a).

### GPT/Codex and Expanded Model Matrix

- Added `src/vao/agents/openai_responses_adapter.py`, a strict OpenAI Responses API transport that reuses the existing C(a) batched structured-edit parser/materializer.
- Registered `openai_responses` in the orchestrator.
- Added strict aliases for `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, `gpt-5.3-codex-spark`, and `gpt-5.2-codex`. These use one Responses API call per step, JSON schema output, and no batch repair.
- Added strict Claude aliases for Sonnet and Opus 4.6 through the same Claude CLI transport as Haiku: `claude_sonnet_batch_strict` and `claude_opus_4_6_batch_strict`.
- Added `qwen_coder_batch_strict` as the clearer alias for the validated Qwen Coder OpenAI-compatible endpoint.
- Added `configs/hard_single_prompt_model_matrix.yaml` containing the requested backend list: GPT-5.4, GPT-5.4-mini, GPT-5.3-Codex, GPT-5.3-Codex-Spark, GPT-5.2-Codex, Qwen Coder, Haiku, Sonnet, and Opus 4.6.
- Added unit tests for OpenAI Responses request construction, output extraction, and six-branch batch materialization. Tests use mocks and do not require live OpenAI calls.

### Codex CLI Live Model Smokes

- Added `src/vao/agents/codex_cli_adapter.py`, a Codex CLI transport for environments where local Codex authentication works but `OPENAI_API_KEY` is not exported.
- Switched the GPT/Codex strict matrix aliases to `adapter: codex_cli`. The OpenAI Responses adapter remains available for direct API-key environments.
- The first Codex CLI full-step smoke with `--output-schema` failed because the OpenAI/Codex strict schema validator requires all nested properties to be listed in `required`; the framework's candidate-edit schema has optional edit keys. Updated Codex CLI transport to place the schema in the prompt and rely on local parser/validator enforcement.
- Validated one-step C(a) smokes:
  - `gpt-5.4`: `runs/hard_profile/single_prompt/model_matrix/hard_gpt54_codex_cli_single_prompt_smoke_1step_r0`, 1 step, 6 branches, `vao.validate_run` passed.
  - `gpt-5.4-mini`: `runs/hard_profile/single_prompt/model_matrix/hard_gpt54mini_codex_cli_single_prompt_smoke_1step_r1`, 1 step, 6 branches, `vao.validate_run` passed.
  - `gpt-5.3-codex`: `runs/hard_profile/single_prompt/model_matrix/hard_gpt53codex_codex_cli_single_prompt_smoke_1step_r0`, 1 step, 6 branches, `vao.validate_run` passed.
  - `gpt-5.3-codex-spark`: `runs/hard_profile/single_prompt/model_matrix/hard_gpt53codexspark_codex_cli_single_prompt_smoke_1step_r0`, 1 step, 6 branches, `vao.validate_run` passed.
- `gpt-5.2-codex` is not available through the current Codex ChatGPT account; the CLI returned `invalid_request_error: model is not supported when using Codex with a ChatGPT account`.
- A full Sonnet C(a) smoke timed out at 600 seconds before producing `evaluations.jsonl`. Minimal CLI probes for Haiku, Sonnet, and Opus 4.6 succeeded, but Sonnet/Opus still need full-step validation before inclusion in a sweep.
- Validation after changes: `pytest -q` passed with 70 tests; `python -m vao.verifier --smoke_test` passed; `vao.validate_run` passed for Haiku, Qwen Coder, and all four completed GPT/Codex full-step smokes.

### Diagnostic Run Cleanup

- Removed raw failed, superseded, or incomplete diagnostic run directories that were adding noise under `runs/`.
- Kept validated primary runs and compact summary artifacts used by current reports.
- Wrote cleanup manifests: `artifacts/diagnostic_run_cleanup_2026_04_22.json` and `artifacts/diagnostic_run_cleanup_2026_04_22.md`.

### Config And Artifact Cleanup

- Reduced `configs/` from historical phase/smoke configs to the active experiment surface: model/profile definitions, local smoke, Haiku/Qwen hard-profile runs, prompt-controlled single-prompt runs, model matrix, C(b), teacher/student, and offline routing configs.
- Removed superseded Phase 1/2/3/3.5 configs and obsolete one-off smoke configs.
- Removed stale artifacts from old phase experiments, superseded smokes, raw probes, intermediate R0/R0-R2 summaries, and obsolete diagnostic reports.
- Regenerated `artifacts/routing_choice_summary.json` and `artifacts/routing_choice_visuals.md` using only current retained routing datasets.
- Added `configs/README.md`, `artifacts/README.md`, and `artifacts/MANIFEST.json` as the active catalogs.
