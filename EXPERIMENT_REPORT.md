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

Resume with a small `structured_edits` C(a) smoke first. If it validates, use `structured_edits` for the next teacher collection; keep `claude_opus_teacher_replacement_legacy` only as a fallback. The moderate Phase 4 matrix remains:

- Dev: 3 profiles x 3 repeats x 5 steps = 45 teacher steps
- Optional holdout: 2 profiles x 2 repeats x 5 steps = 20 teacher steps
- Total target if budget permits: 65 teacher steps

Based on current Opus logs, projected serial cost/time is approximately:

- Dev-only: about `$80.09` and `8.04` serial hours
- Dev plus holdout: about `$115.69` and `11.61` serial hours

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
