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
- Shared-checkpoint controlled phi is not yet fully implemented.
- C(b) pre/post feedback-use diagnostics are implemented and locally validated, but have not yet been run with a live Claude/teacher model because quota is unavailable.
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

## Phase 3.5 Patch-Based Refactor and Revalidation

Phase 3.5 implemented true branch-local patch editing and revalidated C(a). The patch protocol creates the same six branch workspaces, asks Claude for one `unified_diff` per mode, saves that patch as `model_edit.diff`, applies it to the branch parent, materializes `proposed_solution.py`, evaluates all six branches, and promotes only top-1 by `mode_probs`.

Patch runs:

- Smoke V2: `runs/phase35_patch/haiku_smoke/haiku_patch_smoke_v2`
- Dev: `runs/phase35_patch/haiku_dev/haiku_patch_dev_claude_haiku_paper_development`
- Dev: `runs/phase35_patch/haiku_dev/haiku_patch_dev_claude_haiku_memory_development`
- Dev: `runs/phase35_patch/haiku_dev/haiku_patch_dev_claude_haiku_development`

Validation:

- `pytest -q`: 31 passed.
- `PYTHONPATH=src:. python -m vao.verifier --smoke_test`: passed.
- `vao.validate_run`: passed for the corrected smoke and all three dev runs.

Artifacts:

- `artifacts/phase35_patch_summary.json`
- `artifacts/phase35_patch_failure_modes.json`
- `artifacts/phase35_patch_estimators.csv`
- `artifacts/phase35_patch_routing_dataset.jsonl`
- `artifacts/phase35_patch_vs_replacement.json`

Patch dev summary:

- Runs: 3
- Steps: 9
- Branch evaluations: 54
- Average wall-clock per step: `435.12574399842157` seconds
- Average cost per step: `0.5358607722222222` USD
- Mean routing regret: `1.5526810046891615`
- Best visible loss: `0.48901087929497367`
- Best counterfactual loss: `0.48753714261372894`
- Parse/repair/rejection failure rate: `0.18518518518518517`
- Source validation failure rate: `0.12962962962962962`
- Verifier failure rate: `0.18518518518518517`

## Production Protocol Decision

The frozen production protocol for teacher-data generation is C(a) with full replacement-file candidate outputs.

Reason: patch-based editing is semantically closer to literal code editing, but it is not yet the better production data protocol. On dev-to-dev comparison, patch-based Haiku was slower (`435.12574399842157` s/step vs `340.8956255912781` s/step), costlier (`0.5358607722222222` USD/step vs `0.46949549444444444`), and less stable than replacement-file generation. Patch mode remains useful for future method work, but teacher data should use the replacement-file protocol now so the project can move to Opus teacher data and routing-only post-training.

Update: this decision is superseded for future runs by the later `structured_edits` protocol, which is designed to preserve local edit semantics without unified-diff fragility. The replacement-file protocol remains as a legacy fallback.

## Phase 4 Teacher Experiments

Teacher backend: Claude Opus through the already authenticated Claude CLI transport. The local CLI mapped `--model opus` to `claude-opus-4-6`.

Pilot:

- Runs: 3
- Steps: 9
- Branch evaluations: 54
- Average wall-clock per step: `643.0542123052809` seconds
- Average agent cost per step: `1.7984121666666668` USD
- Correctness rate: `1.0` for every declared mode
- Mean routing regret: `1.1281139870550456`
- Mean JSD: `0.5378889006272523`
- Best visible loss: `0.6531563169239188`
- Best counterfactual loss: `0.6247162061075843`
- Parse/repair/rejection failure rate: `0.1111111111111111`
- Code validation failure rate: `0.12962962962962962`
- Verifier failure rate: `0.0`

Production collection:

- Target matrix: 3 dev profiles x 3 repeats/profile x 5 steps/run.
- Completed usable production data: one partial run, `runs/phase4_teacher_opus/opus_teacher_dev_r0`, with 3 validated steps and 18 branch evaluations.
- Failure mode: `claude_cli_failed:1` during the next distribution call. The failed call produced no additional step record.
- Decision: do not hammer the CLI after the failure. Use only validated steps and record the incomplete matrix explicitly in `artifacts/phase4_teacher_run_index.json`.

Combined validated teacher dataset:

- Validated runs: 4
- Validated steps: 12
- Branch evaluations: 72
- Routing records: 12 in `artifacts/phase4_teacher_routing_dataset.jsonl`
- Artifacts: `artifacts/phase4_teacher_dev_summary.json`, `artifacts/phase4_teacher_dev_estimators.csv`, `artifacts/phase4_teacher_dev_failure_modes.json`, `artifacts/phase4_teacher_run_index.json`

Teacher data quality is sufficient for plumbing and a first routing-only experiment, but not sufficient for a strong post-training claim. The dataset is small, contains repair/no-op events, and covers only one validated partial production repeat beyond the pilot.

## Phase 5 Routing-Only Post-Training

Training setup:

- Dataset: `artifacts/phase4_teacher_routing_dataset.jsonl`
- Records: 12
- Train/eval split: 9/3
- Student: TF-IDF plus logistic-regression router saved at `training/phase5_routing_student/model.pkl`
- LoRA status: not used because `peft` and `trl` are unavailable in the current environment.

Offline eval on the tiny held-out split:

- Top-1 productive-mode accuracy: `0.3333333333333333`
- Original top-1 accuracy: `0.0`
- Student predicted top-1 regret: `0.3552415586184802`
- Original top-1 regret: `1.8929338747685003`
- Student predicted JSD: `0.4982921482896754`
- Original JSD: `0.6960718717431963`

Online controlled routing-only eval:

- Setup: deterministic local-stub candidate edits for all branches; only router `mode_probs` differ.
- Baseline local-stub runs: 3
- Routing-student runs: 3
- All 6 online runs passed `vao.validate_run`.
- Local-stub mean routing regret: `0.41225891166210665`
- Student mean routing regret: `0.9519646135760867`
- Local-stub average best loss: `0.5609087939479241`
- Student average best loss: `0.9289299822748313`

Conclusion:

- The C(a) framework is validated. Replacement-file teacher runs are validated historically; future teacher runs should first smoke-test `structured_edits`.
- The teacher pipeline works, but Opus collection is currently budget/availability limited.
- The routing student improved offline regret/JSD on a very small held-out split but did not improve online behavior.
- Before within-mode or feedback-use post-training, collect more validated teacher data, replace the TF-IDF router with a LoRA-capable local model when dependencies are available, and rerun the routing-only evaluation.

## Offline Dataset Audit Without New Teacher Runs

Claude quota is unavailable, so the current milestone used only the existing validated teacher dataset in `artifacts/phase4_teacher_routing_dataset.jsonl`. No Claude, Opus, Haiku, Anthropic API, Claude CLI, Qwen, or new teacher generation was used.

Dataset audit:

- Examples: `12`
- Profiles: `paper_development` 6, `development` 3, `memory_development` 3
- Productive modes: `layout` 6, `indexing` 3, `micro` 2, `caching` 1, `topk` 0, `summaries` 0
- Selected teacher modes: `layout` 5, `topk` 3, `summaries` 2, `indexing` 2, `caching` 0, `micro` 0
- Class imbalance max/min nonzero ratio: `6.0`
- Original teacher top-1 routing regret: mean `0.9385370051379591`, median `0.35313465405577155`, max `4.217488474179428`, positive on 8 of 12 examples
- Declared/inferred branch-mode agreement: `0.4722222222222222` across 72 branch records
- Near-duplicate state pairs: `6`, mostly initial checkpoints

Artifacts:

- `artifacts/offline_routing_dataset_audit.json`
- `artifacts/offline_routing_dataset_audit.md`

The audit confirms that the dataset is usable for replay tooling and bottleneck analysis, but not for a strong learned-router claim. `topk` and `summaries` have no productive-mode labels, and `layout` is overrepresented.

## Replay-Based Routing Evaluation

Added one-step logged-counterfactual replay in `src/vao/analysis/replay_routing.py`. Replay evaluates alternate routing policies at checkpoints where all six branch outcomes are already logged. It does not simulate future checkpoints after an alternate branch promotion, so results are online-like diagnostics rather than true live online experiments.

Replay headline metrics:

| policy | accuracy | top-1 regret | expected regret |
| --- | ---: | ---: | ---: |
| `original_teacher` | `0.3333333333333333` | `0.9385370051379591` | `0.9438246618709512` |
| `saved_routing_student` | `0.5` | `0.19060538911168567` | `0.4924397490840365` |
| `always_layout` | `0.5` | `0.3347770188314449` | `0.3347770188314449` |
| `frequency_baseline` | `0.5` | `0.3347770188314449` | `0.4588127976786531` |
| `random_seeded` | `0.16666666666666666` | `0.8173871052726692` | `0.8173871052726692` |

The prior saved routing student has the lowest top-1 regret among nontrivial policies, but `always_layout` has the lowest expected regret because the dataset is strongly layout-heavy. This is a data-quality warning, not a routing breakthrough.

Artifacts:

- `artifacts/replay_router_comparison.json`
- `artifacts/replay_router_comparison.md`
- `artifacts/replay_online_like_summary.json`
- `artifacts/replay_online_like_summary.md`

## Offline Progress During Claude Quota Pause

Classical/local student work:

- Added stronger routing features including profile, step, source-code indicators, and visible-history selected-mode counts.
- Ran leave-one-out comparisons for TF-IDF word logistic regression, TF-IDF char logistic regression, TF-IDF multinomial Naive Bayes, and structured-feature logistic regression.
- Selected model by leave-one-out expected regret: `tfidf_word_multinomial_nb`.
- Best classical model metrics: accuracy `0.5`, macro F1 `0.1111111111111111`, weighted F1 `0.3333333333333333`, expected regret `0.45382518397291854`, top-1 regret `0.3347770188314449`.

Local fine-tuning stack:

- Installed `peft==0.19.1` and `trl==1.2.0`; existing local versions include `torch==2.10.0`, `transformers==5.3.0`, `datasets==4.7.0`, and `accelerate==1.13.0`.
- Skipped `bitsandbytes` on macOS arm64 because it is CUDA-oriented.
- Ran a toy PEFT LoRA smoke test with no external model calls; loss decreased and train accuracy reached `1.0`.
- Trained a cached `distilbert-base-uncased` LoRA sequence classifier locally with `local_files_only=True`.
- Local LoRA training loss decreased from `1.7637574672698975` to `0.5818454623222351`.
- Local LoRA eval on the tiny 3-example split predicted only `layout`: accuracy `0.3333333333333333`, expected regret `1.0319806536763083`, top-1 regret `1.061226882285533`.

Artifacts:

- `training/offline_routing_student/model.pkl`
- `training/offline_routing_student_lora/`
- `artifacts/offline_routing_train_summary.json`
- `artifacts/offline_routing_eval_summary.json`
- `artifacts/offline_routing_model_comparison.json`
- `artifacts/offline_router_leaderboard.json`
- `artifacts/offline_router_leaderboard.md`
- `artifacts/local_lora_smoke.json`
- `artifacts/local_training_stack_audit.json`
- `artifacts/offline_lora_router_summary.json`
- `artifacts/offline_lora_router_predictions.json`

## What Prevents Routing Improvement Right Now

Main bottlenecks:

- The routing dataset has only 12 examples.
- Two canonical modes, `topk` and `summaries`, have zero productive labels.
- `layout` dominates both positive labels and expected-regret baselines.
- Several initial checkpoints are near duplicates, reducing effective diversity.
- Teacher top-1 routing is often suboptimal on the logged counterfactuals, with positive regret on 8 of 12 examples.
- Labels are partly ambiguous: 7 examples have multiple positive-gain modes and 2 examples have multiple modes within 0.05 verified gain of the best mode.
- Declared/inferred mode agreement is low for `indexing`, `micro`, and `summaries`, which adds target noise for mode-conditioned analysis.

Hardest profile under the selected offline model is `development`, with accuracy `0.0` and mean regret `1.0216142494473144`. `memory_development` is easiest on this tiny sample, with accuracy `1.0` and mean regret `0.0`.

The correct next scientific step is not more offline model tuning on these 12 records. It is more validated, balanced teacher data once quota returns.

## Next Step Once Teacher Budget Returns

Resume with a small batched `structured_edits` C(a) smoke first. If it
validates, use the same `single_step_program.txt` path for the next teacher
collection. The moderate Phase 4 dev matrix is:

- Dev: 3 profiles x 3 repeats x 5 steps = 45 teacher steps
- Final holdout evaluation after model/protocol freeze: 3 profiles x 2 repeats x 5 steps = 30 steps
- Total target if budget permits: 75 evaluated steps, with only dev used for post-training

Based on current Opus logs, projected serial cost/time is approximately:

- Dev-only: about `$80.09` and `8.04` serial hours
- Dev plus final holdout evaluation: about `$133.48` and `13.40` serial hours

Detailed resume checklist and run-manifest plan are in `artifacts/future_teacher_scaling_plan.md`. After collecting more data, rerun the dataset audit, replay leaderboard, classical routing comparisons, and local LoRA routing experiment before attempting within-mode or feedback-use training.

## Structured Edit Protocol Debug

The previous production protocol asked the model for complete replacement `solution.py` files. That was reliable, but it does not measure the cost of small line edits. The earlier `unified_diff` patch protocol reduced output length but failed too often because model-generated hunks were malformed, ambiguous, or needed repair.

New default candidate protocol for future Claude runs:

- `edit_format: "structured_edits"`
- supported operations: `replace_exact`, `delete_exact`, `insert_before`, `insert_after`, `replace_function`
- the framework still creates six isolated branch copies, one per mode
- the model returns compact edit operations, not a full file
- the harness applies edits locally, materializes `proposed_solution.py`, validates source safety, then runs the verifier

Observed/debug numbers:

- Phase 3 Haiku replacement: mean raw candidate output about `3706` chars
- Phase 4 Opus replacement: mean raw candidate output about `3738` chars
- Phase 3.5 unified diff: mean raw candidate output about `2958` chars, but many repair/apply failures
- Structured one-line edit example: `219` chars
- Structured function-replacement example: `533` chars
- Full template replacement payload example: `2496` chars

Decision: use `structured_edits` as the default real-model edit protocol when budget returns. Legacy replacement and unified-diff configs remain for fallback comparisons.

Artifact: `artifacts/edit_protocol_debug_report.md`.

## Haiku Batch Speed Check

The first live test of `structured_edits` was still slow because it made seven serial Claude calls per step: one distribution call plus one candidate-generation call per mode. That repeated the parent source/context six times, so shorter edit payloads did not translate into lower wall-clock time.

I added a batched path where one Haiku call returns `mode_probs`, `mode_ranking`, and all six structured-edit candidates. The harness still creates six isolated branch copies, applies each branch-local edit independently, evaluates all six offline, and promotes only the top-1 mode by normalized `mode_probs`.

Observed 1-step Haiku smoke:

| protocol | sec/step | USD/step | input tokens/step | output tokens/step |
|---|---:|---:|---:|---:|
| replacement smoke | `326.4` | `0.479` | `332968` | `48314` |
| structured edits, six calls | `480.4` | `0.629` | `331817` | `72751` |
| structured edits, one batch call | `132.7` | `0.179` | `64324` | `24346` |

Conclusion: the credible speed path is batched structured editing, not six separate mode calls. The batch smoke passed `vao.validate_run`, but one `indexing` candidate was rejected by source safety validation and logged as an explicit no-op. Before scaling teacher runs, batch mode needs a slightly larger quality smoke and prompt/repair tightening for source-safety failures.

Artifacts:

- `runs/phase3_real_backend/haiku_structured_batch_smoke/haiku_structured_batch_speed`
- `artifacts/haiku_batch_speed_debug_report.json`
- `artifacts/haiku_batch_speed_debug_report.md`

## Single Hard Benchmark Profile

The active benchmark profile set has been collapsed to one canonical profile, `hard_optimization`. This removes profile-selection ambiguity for the next round of experiments and makes every new run target the same difficult mixed workload.

Profile design:

- all nine workload families are included;
- `initial_size=2600`;
- `key_space=120000`;
- `trace_length=1200`;
- `traces_per_family=1`;
- `repetitions=2`;
- `warmup_prefix=120`.

The point is to avoid an easy single-mode workload. The profile simultaneously pressures point lookups, hot-key access, bursty updates, local and wide range queries, distribution shifts, repeated windows, top-k queries, and negative lookup/delete churn. This should make routing errors more informative because different modes can plausibly help or hurt depending on the current parent solution.

Historical artifacts still contain older profile names because they describe past runs. New configs and defaults now point to `hard_optimization`.

## Hard Profile Experiment Readiness

The hard-profile experiment path is now validated locally and with one live Haiku batch run.

Validated configs:

- `configs/hard_local_smoke.yaml`
- `configs/hard_local_dev.yaml`
- `configs/hard_haiku_batch_smoke.yaml`
- `configs/hard_haiku_batch_pilot.yaml`

Validated runs:

| run | steps | branches | total sec/step incl. baseline | post-baseline sec/step | cost |
|---|---:|---:|---:|---:|---:|
| local hard smoke | `1` | `6` | `143.1` | `78.6` | n/a |
| local hard 2-step calibration | `2` | `12` | `111.0` | `78.2` | n/a |
| Haiku batch hard smoke | `1` | `6` | `346.4` | `282.4` | `$0.171` |

All three runs passed `vao.validate_run`. The Haiku batch hard smoke had zero proposal failures, zero source-validation failures, and zero verifier failures. The current practical pilot size is therefore 3 steps: roughly 15 minutes serial wall-clock and about `$0.51` in Haiku CLI cost, plus variance from generated candidate speed.

The first 3-step Haiku batch pilot has now been run and validated:

| run | steps | branches | total sec/step incl. baseline | post-baseline sec/step | total cost |
|---|---:|---:|---:|---:|---:|
| Haiku batch hard pilot | `3` | `18` | `269.0` | `247.7` | `$0.600` |

Pilot details:

- selected modes: `layout`, `caching`, `summaries`;
- best visible loss: `0.28242576429393895`;
- best counterfactual loss: `0.2784324758473186`;
- mean routing regret: `0.009569049696577977`;
- proposal/source-validation failure rate: `0.111`;
- incorrect branch rate: `0.056`;
- verifier infrastructure failure rate: `0.000`.

The two proposal failures were rejected safely because generated code used banned `list.remove` calls. The incorrect branch was a `topk` candidate with a semantic tie-breaking/correctness mismatch. Both are logged as counterfactual evidence and do not break the C(a) trajectory.

Follow-up bugfixes:

- `.remove(...)` rejection: added deterministic parser repair for simple statement-level `container.remove(value)` calls when this is the only source-validation error. The repair rewrites to a list-comprehension assignment, revalidates the full source, and logs `source_repair_status` plus `source_repairs`.
- `top_k` semantic error: hardened prompts to explicitly require value-descending, key-ascending ordering with semantics equivalent to `(-value, key)`.
- No local semantic repair is applied to wrong `top_k` algorithms; the verifier remains the correctness authority for these branches.

Artifacts:

- `artifacts/hard_profile_experiment_readiness.json`
- `artifacts/hard_profile_experiment_readiness.md`
- `artifacts/hard_local_dev_2step_summary.json`
- `artifacts/hard_haiku_batch_smoke_summary.json`
- `artifacts/hard_haiku_batch_pilot_readout.md`
- `artifacts/hard_haiku_batch_pilot_summary.json`
- `artifacts/hard_pilot_bugfix_report.md`
- `artifacts/hard_qwen_batch_smoke_summary.md`
- `artifacts/plots/run_hard_local_dev_2step_calibration/`
- `artifacts/plots/run_hard_haiku_batch_smoke_1step/`
- `artifacts/plots/run_hard_haiku_batch_pilot_3step/`
- `artifacts/plots/run_hard_qwen_batch_smoke_1step/`

## Qwen Weak-Model Smoke

The first open-weight weak model smoke used `Qwen/Qwen2.5-Coder-1.5B-Instruct`:
small, ungated, code-oriented, and runnable on one Engaging L40S GPU. This
section is historical because the first smoke used a fallback path. Current
prompt-controlled Qwen comparisons should use `qwen_coder_batch_strict`, which
does not fall back to per-mode prompts.

Implementation details:

- Qwen Coder uses the real `OpenAICompatibleAdapter` instead of a local-stub fallback.
- The adapter targets `/v1/chat/completions` and can run against vLLM/SGLang or the minimal `scripts/qwen_openai_compat_server.py` server.
- Qwen 1.5B could produce a valid mode distribution, but its first all-in-one `mode_probs + six edits` batch response was malformed. The historical adapter fell back to Qwen distribution plus six Qwen per-mode structured-edit calls. That fallback is no longer part of active prompt-controlled experiments.
- Added deterministic parser repairs for fenced/triple-quoted JSON and unindented replacement method bodies. These repairs do not bypass source validation or verifier evaluation.

Validated run:

| run | model | steps | branches | wall sec/step | input tokens | output tokens | validation |
|---|---|---:|---:|---:|---:|---:|---|
| `hard_qwen_batch_smoke_1step` | `Qwen/Qwen2.5-Coder-1.5B-Instruct` | `1` | `6` | `240.9` | `11658` | `1729` | passed |

Qwen selected `layout` with normalized mode probabilities:

```json
{"layout": 0.3, "indexing": 0.2, "topk": 0.2, "caching": 0.1, "summaries": 0.1, "micro": 0.1}
```

The selected visible branch improved loss from `1.001238` to `1.000535`. The best counterfactual branch was `topk` with loss `0.999924`, producing routing regret `0.000610`. This is useful as a weak-router smoke: Qwen follows the protocol enough to generate a logged six-branch tensor, but it is not yet a high-quality teacher.

Artifacts:

- `artifacts/hard_qwen_batch_smoke_summary.json`
- `artifacts/hard_qwen_batch_smoke_summary.md`
- `artifacts/hard_qwen_batch_smoke_estimators.csv`
- `artifacts/hard_qwen_batch_smoke_routing_dataset.jsonl`
- `artifacts/plots/run_hard_qwen_batch_smoke_1step/`

## Historical LangGraph Direct-File Editing

An optional direct-file-edit backend was implemented for Qwen-style open-weight
experiments. It has now been removed from the active code/config/test surface
because it is not a single-prompt experiment path.

What changed:

- The historical `weak_qwen_direct` alias used a direct-edit adapter.
- The model first produces the usual mode distribution.
- For each mode branch, a LangGraph loop lets the model call restricted tools that edit only that branch's `proposed_solution.py`.
- The tool layer, not the model shell, performs the actual file operation. Allowed operations are exact text replacements, inserts, deletes, whole-function replacement, validation, and finish.
- The model cannot access the terminal, the shared parent, or other branch directories in this backend.

This satisfied the requested "directly modify the file" behavior while
preserving C(a), but it required a routing prompt plus six per-mode tool loops.
Therefore it is now treated as a historical diagnostic path, not an active
Haiku/Qwen/GPT comparison path.

## C(b) Feedback-Use Diagnostic Infrastructure

C(b) is now implemented as an optional protocol condition, without running any new Claude calls.

Configuration:

- `feedback_condition: cb`
- `visibility_regime: all_branches`
- `ask_post_feedback_distribution: true`
- `selection_policy: top1`, `fixed_mode`, or `mode_sequence`

Logged per step:

- `mode_probs`: pre-feedback distribution `q_pre`
- `post_feedback_mode_probs`: post-feedback distribution `q_post`
- `selected_mode_top1`: model argmax before any controlled override
- `selected_mode`: branch actually promoted
- `feedback_regret_improvement`: `epsilon_pre - epsilon_post`
- `feedback_jsd_improvement`: `JSD(q_pre, p*) - JSD(q_post, p*)`

Local smoke:

- Run: `runs/feedback_use_cb/cb_local_fixed_micro`
- Steps: 2
- Branch evaluations: 12
- Selection policy: fixed promotion of `micro`
- Validation: `vao.validate_run` passed

Because the smoke uses `local_stub`, `q_post` is identical to `q_pre` and feedback improvement is zero. That is expected; the smoke proves the logging and validation path. A meaningful estimate of `G` requires a live model to revise its distribution after seeing verifier feedback.

## Diagnostic Visualizations

Added per-run visual diagnostics in `src/vao/analysis/run_diagnostics_visuals.py`.

For each run it can produce:

- mode probability trajectories by step
- single-mode probability/gain trajectory across steps
- latent loss by step and mode
- verified gain heatmap by step and mode
- token/USD cost by step
- C(b) pre/post probability comparison when `post_feedback_mode_probs` exists

Generated plots are under:

- `artifacts/plots/run_cb_local_fixed_micro/`
- `artifacts/plots/run_opus_teacher_pilot_claude_opus_teacher_paper_development/`
- `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_development/`
- `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/`
- `artifacts/plots/run_opus_teacher_dev_r0/`

## Haiku vs Qwen Hard-Profile R0

The first direct comparison is complete and validated. It uses the frozen C(a) visibility rule in both runs: every step generates six branches from one parent, all branches are evaluated offline, and only the top-probability branch is promoted as the next visible state.

| model/backend | steps | branches | sec/step | routing acc | mean regret | branch correct | best visible | best counterfactual | cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku batch structured edits | 10 | 60 | 302.7 | 0.20 | 0.4085 | 0.83 | 0.1860 | 0.1090 | `$1.940` |
| Qwen 1.5B direct-file edit | 10 | 60 | 181.0 | 0.20 | 0.0140 | 1.00 | 0.9708 | 0.9690 | `$0` local |

Key readout:

- Qwen direct-file editing is now a working baseline, not just a scaffold. It ran on an Engaging L40S through the OpenAI-compatible local server and passed `vao.validate_run`.
- Qwen was faster in this R0 and generated far fewer output tokens, but it selected `layout` in 9 of 10 steps and made only small loss improvements.
- Haiku explored more modes and found much stronger counterfactual branches, but its visible trajectory was less stable: selected branches were incorrect at steps 0 and 9.
- Both routers chose the verified-best mode only 2 out of 10 times. This gives useful routing-regret signal, but one repeat is not enough for a final model ranking.
- The comparison is not a pure model ablation because Haiku used batched structured edits while Qwen used LangGraph direct branch-local editing. Treat it as a first system-level protocol run.

Artifacts:

- `artifacts/haiku_vs_qwen_10step_r0_summary.json`
- `artifacts/haiku_vs_qwen_10step_r0_summary.md`
- `artifacts/haiku_vs_qwen_10step_r0_estimators.csv`
- `artifacts/haiku_vs_qwen_10step_r0_routing_dataset.jsonl`
- `artifacts/plots/run_hard_haiku_batch_10step_r0/`
- `artifacts/plots/run_hard_qwen_direct_10step_r0/`

## Haiku vs Qwen Hard-Profile R0-R2

The comparison now has three validated repeats per backend: 6 total runs, 60 total steps, and 360 branch evaluations.

| backend | runs | steps | sec/step | routing correct | mean regret | branch correct | selected correct | best visible | best counterfactual | cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku batch structured edits | 3 | 30 | 251.4 | 5/30 | 0.4248 | 0.67 | 0.63 | 0.1652 | 0.1010 | `$5.626` |
| Qwen 1.5B direct-file edit | 3 | 30 | 188.4 | 4/30 | 0.0167 | 1.00 | 1.00 | 0.9708 | 0.9690 | `$0` local |

Main conclusions:

- Haiku remains the stronger optimizer. It found the best visible and counterfactual losses by a wide margin.
- Qwen direct remains the safer weak baseline. Across 180 branch evaluations, all branches were verifier-correct and all selected branches were correct.
- Qwen routing is conservative: it selected `layout` 27/30 times, while verified-best branches were spread across all modes.
- Haiku routing is more diverse but still weak: 5/30 selected modes matched the best verified branch.
- Mean regret is not directly comparable as model quality alone because Haiku sometimes takes large incorrect-branch penalties while Qwen mostly makes small but safe local edits.

For this report, "best mode" is the declared branch mode with minimum verified `latent_loss` at that step. This keeps the six controlled C(a) branch identities distinct from the diff-inferred mode classifier.

Artifacts:

- `artifacts/haiku_vs_qwen_10step_r0_r2_summary.json`
- `artifacts/haiku_vs_qwen_10step_r0_r2_summary.md`
- `artifacts/haiku_vs_qwen_10step_r0_r2_estimators.csv`
- `artifacts/haiku_vs_qwen_10step_r0_r2_routing_dataset.jsonl`

## Haiku vs Qwen Hard-Profile R0-R4

The comparison now has five validated repeats per backend: 10 total runs, 100 total steps, and 600 branch evaluations.

| backend | runs | steps | sec/step | routing correct | mean regret | branch correct | selected correct | best visible | best counterfactual | cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Haiku batch structured edits | 5 | 50 | 242.1 | 10/50 | 0.5583 | 0.61 | 0.56 | 0.1107 | 0.1010 | `$9.165` |
| Qwen 1.5B direct-file edit | 5 | 50 | 203.9 | 12/50 | 0.0114 | 1.00 | 1.00 | 0.9708 | 0.9690 | `$0` local |

Main conclusions:

- Qwen direct remains the safer weak baseline: every branch and every promoted branch was verifier-correct across 300 branch evaluations.
- Haiku remains the better optimizer: its best visible and counterfactual losses are far below Qwen's, meaning it finds much stronger edits when it succeeds.
- Qwen routing is still conservative: it selected `layout` 47/50 times, while the verified-best branch was spread across all six modes.
- Haiku routing is more diverse but less reliable: selected branches were correct only 56% of the time, and failed/slow candidates materially affect regret and runtime.
- Three partial Haiku trials were excluded from the aggregate because they did not complete 10 validated steps after `claude_cli_failed:1`.

Definitions used here:

- `best visible`: the lowest verified loss along the actually promoted C(a) trajectory.
- `best counterfactual`: the lowest verified loss among all offline-evaluated branches, including invisible branches.
- `branch correct`: fraction of all candidate branch files that passed semantic verifier correctness; it does not mean the branch improved performance.

Artifacts:

- `artifacts/haiku_vs_qwen_10step_r0_r4_summary.json`
- `artifacts/haiku_vs_qwen_10step_r0_r4_summary.md`
- `artifacts/haiku_vs_qwen_10step_r0_r4_estimators.csv`
- `artifacts/haiku_vs_qwen_10step_r0_r4_routing_dataset.jsonl`
- `artifacts/haiku_vs_qwen_10step_r0_r4_visuals.md`
- `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/`
- `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/`
- `artifacts/plots/run_hard_qwen_direct_10step_r3/`
- `artifacts/plots/run_hard_qwen_direct_10step_r4/`

## R0-R4 Failure Analysis and Fixes

Before launching more model runs, I audited the failure surface.

Findings:

- Haiku is optimization-capable but fragile: 118/300 branches were incorrect or non-finite. Failures are not isolated to one mode; they appear across layout, indexing, topk, caching, summaries, and micro.
- The dominant Haiku failure family is semantic/API breakage: mixed storage representations, broken aggregate_count, top_k ordering mistakes, import/runtime errors, and occasional slow candidates.
- Qwen is safe but conservative: 300/300 branches were verifier-correct, but it selected `layout` 47/50 times while the verified-best branch was often non-layout.

Implemented fixes:

- Added a fast verifier preflight before the full benchmark. It runs deterministic API checks against the reference engine and catches constructor, get/put/delete, range_sum, aggregate_count, and top_k ordering failures.
- Historical replay shows the preflight would catch 99/118 invalid Haiku branches with 0 false rejects on correct branches.
- Hardened prompts so storage-layout changes must update all dependent methods, aggregate_count must count keys under inclusive bounds, and top_k must preserve value-desc/key-asc order.
- Hardened routing prompts to discourage the Qwen layout-default pattern and to lower recently poor selected modes.

This should reduce wasted verifier time and reduce obvious semantic failures in the next smoke. It does not change C(a): every branch still gets a logged offline evaluation outcome, and only the selected branch is visible/promoted.

Artifacts:

- `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.json`
- `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.md`

## Prompt-Control and Preflight Clarification

Preflight is not part of the model prompt. It is a local verifier-side check that runs after a candidate branch has been materialized and before the full benchmark spends time on it. It therefore does not advantage Haiku or Qwen through different instructions; it only changes how invalid generated code is diagnosed and short-circuited.

The existing R0-R4 Haiku/Qwen matrix should be interpreted as a system/backend comparison, not a pure prompt-controlled model comparison. Haiku used one batched structured-edit prompt per step. Qwen direct used the same routing interface plus six LangGraph direct-file-edit loops. Those paths were intentionally chosen for speed and edit realism, but they are not byte-identical prompts.

To fix this going forward, all real-model prompt paths now include the shared `CANONICAL_TASK_BLOCK_V1`: same six modes, same `CandidateQueryEngine` API, same branch isolation and anti-leakage rule, same safety constraints, same `top_k` and `aggregate_count` semantics, and same routing guidance.

For a pure prompt-controlled Haiku-vs-Qwen ablation, use the single-prompt batched configs:

- `configs/hard_haiku_prompt_controlled_10step.yaml`
- `configs/hard_qwen_prompt_controlled_10step.yaml`

Both use `candidate_generation: batched`: one model-generation prompt per step asks for `mode_probs`, `mode_ranking`, and all six mode-specific structured edits. The strict model aliases disable per-mode fallback and batch repair, so malformed all-in-one output is treated as a real backend failure rather than silently turning into seven prompts.

## Single Active Program Prompt

After the prompt audit, the active C(a) real-model path has been consolidated to
one physical prompt file:

- `src/vao/prompts/single_step_program.txt`

This prompt is adapted as a self-contained experiment program: it defines the
task, the anti-leakage rule, the six modes, the API contract, safety limits, the
probability target, and the structured JSON output in one file. The old shared
and per-mode prompt files are retained only for historical/diagnostic paths and
tests; they are not current prompt-controlled experiment entrypoints.

The prompt now states explicitly that modes are experimental labels, not edit
permissions. A `topk` candidate, for example, may modify `__init__` or helper
state if needed for a coherent correct top-k optimization. The branch's
`primary_mode` records the dominant optimization idea for routing analysis; it
does not restrict which functions or lines may change.

Every new batched run now writes the exact rendered prompt to:

- `steps/step_XXXX/prompt_snapshot.txt`
- `steps/step_XXXX/prompt_snapshot.json`

This closes the previous reproducibility gap where logs stored output text and
prompt hashes but not the full prompt seen by the model.

The legacy prompt files and direct-edit backend have now been removed from the
active code/config/test surface. Real-model runs cannot silently use a
distribution-only prompt, six per-mode edit prompts, direct file-edit loops, JSON
repair prompts, diff prompts, or replacement-file prompts. A configured run must
use `candidate_generation: batched`, otherwise the orchestrator raises an error.

## Single-Prompt Smoke Results

I ran the strict single-prompt path after correcting the configs.

Haiku completed successfully:

- Run: `runs/hard_profile/single_prompt/haiku_batch_structured/hard_haiku_single_prompt_smoke_1step_r0`
- Validation: passed
- Steps: 1
- Branch evaluations: 6
- Wall-clock: 520.3 seconds
- Cost: `$0.2166`
- Branch correctness: 6/6
- Selected mode: `layout`
- Best counterfactual mode: `indexing`
- Selected visible loss: `0.1617`
- Best counterfactual loss: `0.1218`

This confirms that Haiku can satisfy the intended single-prompt batch protocol.
It also produced the desired counterfactual routing signal: the model promoted
`layout`, but the best verified branch was `indexing`.

Qwen Coder on Engaging was not available through the local endpoint during this
smoke, and non-interactive SSH to Engaging failed. I therefore tested the same
strict path with cached local `Qwen/Qwen3-0.6B-Base`. That run completed baseline
verification but failed at the single batch JSON contract with `ModelOutputError:
Extra data`. Per-mode fallback was disabled, so it produced zero branch
evaluations rather than silently becoming seven prompts. This is a valid negative
infrastructure result for the cached local model, not a successful Qwen Coder
comparison.

I then downloaded and served `Qwen/Qwen2.5-Coder-1.5B-Instruct` locally through
the same OpenAI-compatible smoke server on MPS. The first strict attempt reached
the model but returned `candidates` as a list rather than an object keyed by mode.
After adding an explicit JSON skeleton to the single prompt, Qwen Coder passed:

- Run: `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_coder_single_prompt_smoke_1step_r1_promptfix`
- Validation: passed
- Steps: 1
- Branch evaluations: 6
- Wall-clock: 377.7 seconds
- Cost: `$0` local
- Branch correctness: 6/6
- Selected mode: `caching`
- Best counterfactual mode: `micro`
- Selected visible loss: `0.9950`
- Best counterfactual loss: `0.9908`

This establishes that both Haiku and Qwen Coder can now run the intended
single-prompt batched C(a) protocol. Qwen Coder's routing was degenerate in this
smoke, assigning all probability to `caching`, so the next comparison should
measure whether that pattern persists over multiple steps.

Artifacts:

- `artifacts/single_prompt_smoke_readout.json`
- `artifacts/single_prompt_smoke_readout.md`

## Expanded Single-Prompt Model Matrix

The framework now supports the requested hosted and local backends under the
same C(a) single-prompt batch protocol.

GPT/Codex models can use either the direct `openai_responses` adapter or the
new `codex_cli` adapter. The active local matrix uses `codex_cli` because the
machine has Codex CLI authentication but no exported `OPENAI_API_KEY`. The
protocol is still one controlled C(a) model-generation call per step: the model
returns `mode_probs`, `mode_ranking`, and six structured edits, and the
framework materializes/evaluates branch copies locally.

Configured model aliases:

| alias | model |
|---|---|
| `gpt_5_4_batch_strict` | `gpt-5.4` |
| `gpt_5_4_mini_batch_strict` | `gpt-5.4-mini` |
| `gpt_5_3_codex_batch_strict` | `gpt-5.3-codex` |
| `gpt_5_3_codex_spark_batch_strict` | `gpt-5.3-codex-spark` |
| `gpt_5_2_codex_batch_strict` | `gpt-5.2-codex` |
| `qwen_coder_batch_strict` | `Qwen/Qwen2.5-Coder-1.5B-Instruct` |
| `claude_haiku_batch_strict` | Claude Haiku CLI alias |
| `claude_sonnet_batch_strict` | Claude Sonnet CLI alias |
| `claude_opus_4_6_batch_strict` | Claude Opus 4.6 CLI alias |

The matrix config is:

- `configs/hard_single_prompt_model_matrix.yaml`

Live full-step results now available:

| model | run | validation | selected | branch correctness |
|---|---|---|---|---|
| `gpt-5.4` | `hard_gpt54_codex_cli_single_prompt_smoke_1step_r0` | passed | `layout` | 6/6 |
| `gpt-5.4-mini` | `hard_gpt54mini_codex_cli_single_prompt_smoke_1step_r1` | passed | `summaries` | 6/6 |
| `gpt-5.3-codex` | `hard_gpt53codex_codex_cli_single_prompt_smoke_1step_r0` | passed | `indexing` | 6/6 |
| `gpt-5.3-codex-spark` | `hard_gpt53codexspark_codex_cli_single_prompt_smoke_1step_r0` | passed | `topk` | 6/6 |

`gpt-5.2-codex` is not available through the current Codex ChatGPT account. A
full Sonnet single-prompt C(a) smoke timed out at 600 seconds; Haiku, Sonnet,
and Opus 4.6 minimal CLI probes are reachable, but Sonnet/Opus still need
validated full-step runs before being included in a sweep.

## Paper Generalization Split and Launch Readiness

The paper claim requires generalization beyond a single workload profile. The
active benchmark has therefore been expanded from the legacy single
`hard_optimization` profile to three hard task families with paired
development/holdout instances:

- Balanced mixed: `hard_balanced_dev`, `hard_balanced_holdout`
- Range/summary-heavy: `hard_range_dev`, `hard_range_holdout`
- Churn/top-k/update-heavy: `hard_churn_dev`, `hard_churn_holdout`

Development profiles are for prompt debugging, model comparison, teacher data,
and routing-student training. Holdout profiles are reserved for final evaluation
after the protocol/model/training choices are frozen. This fixes the previous
gap where `hard_optimization` was useful for calibration but insufficient for a
generalization claim.

Implemented support:

- `configs/profiles.yaml` now defines dev, holdout, smoke, and legacy groups.
- `src/vao/profile_splits.py` and `src/vao/analysis/profile_split_audit.py`
  audit profile coverage, split overlap, and seed overlap.
- `vao.training.build_routing_dataset` now records `profile_split` and supports
  `--exclude_holdout`, so training datasets can be built without holdout leakage.
- New configs: `configs/paper_profile_local_validation.yaml`,
  `configs/paper_dev_model_comparison.yaml`, and
  `configs/paper_holdout_final_eval.yaml`.
- `configs/phase4_teacher_opus*.yaml` now target the dev split for future
  teacher data collection.

Automatic validation completed without new live model calls:

- Runs: 6 local C(a) runs across all active dev/holdout profiles
- Steps: 6 total
- Branch evaluations: 36 total
- Validation: all six runs passed `vao.validate_run`
- Routing records: 6 all-profile records, 3 dev-only records after
  `--exclude_holdout`
- Mean wall-clock in this reduced local validation: `1.33s/step`
- Branch correctness: `36/36`

Generated artifacts:

- `artifacts/profile_split_audit.json`
- `artifacts/profile_split_audit.md`
- `artifacts/paper_profile_validation_summary.json`
- `artifacts/paper_profile_validation_estimators.csv`
- `artifacts/paper_profile_validation_routing_all.jsonl`
- `artifacts/paper_profile_validation_routing_dev_only.jsonl`
- `artifacts/paper_profile_validation_failure_modes.json`

Recommended next live sequence:

1. Run a short dev split comparison with
   `configs/paper_dev_model_comparison.yaml`.
2. Build dev-only routing data using `--exclude_holdout`.
3. Train/evaluate the routing-only student on dev data.
4. Only then open `configs/paper_holdout_final_eval.yaml` for the final
   held-out generalization test.

## Paper Dev R0: GPT-5.3-Codex-Spark

The first real dev-split run after adding holdout separation used
`gpt-5.3-codex-spark` through the Codex CLI. Qwen was not served on
`localhost:8000` at launch time, so this is a single-backend R0 rather than a
matched model comparison.

Run matrix:

- Profiles: `hard_balanced_dev`, `hard_range_dev`, `hard_churn_dev`
- Repeats: 1
- Steps per profile: 3
- Branches per step: 6
- Total: 3 runs, 9 steps, 54 branch evaluations
- Protocol: C(a), one `single_step_program.txt` prompt per step
- Validation: all three runs passed `vao.validate_run`

Aggregate result:

- Average wall-clock: `105.0s/step`
- Best visible loss: `0.1784`
- Best counterfactual loss: `0.1087`
- Mean routing regret: `0.7856`
- Mean JSD: `0.3554`
- Correct branch rate by mode stayed at or above `0.8889`; aggregate source/parse failure rate was `0.0741`
- Routing top-1 matched a verified-best branch on `2/9` steps

By profile:

| profile | steps | best visible loss | best counterfactual loss | mean routing regret |
| --- | ---: | ---: | ---: | ---: |
| `hard_balanced_dev` | 3 | `0.3093` | `0.1500` | `0.4427` |
| `hard_range_dev` | 3 | `0.9645` | `0.1087` | `1.7882` |
| `hard_churn_dev` | 3 | `0.1784` | `0.1146` | `0.1260` |

The range-heavy task is the clearest routing bottleneck in this R0: the
counterfactual branch tensor contained a much better branch than the visible
route selected online. This is exactly the kind of evidence the framework is
meant to expose before routing post-training.

Artifacts:

- `artifacts/paper_dev_gpt53spark_r0_summary.json`
- `artifacts/paper_dev_gpt53spark_r0_estimators.csv`
- `artifacts/paper_dev_gpt53spark_r0_routing_dataset.jsonl`
- `artifacts/paper_dev_gpt53spark_r0_failure_modes.json`
- `artifacts/paper_dev_gpt53spark_r0_routing_choice_summary.json`
- `artifacts/paper_dev_gpt53spark_r0_routing_choice_visuals.md`
- `artifacts/plots/run_paper_dev_gpt53spark_r0_*`
