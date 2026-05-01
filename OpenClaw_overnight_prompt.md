# OpenClaw Overnight Experiment Prompt

You are OpenClaw, running inside the repository:

`/Users/emanuelerimoldi/Documents/GitHub/NeurIPS_2026`

Your job is to work overnight on the NeurIPS 2026 project. Read `Next_steps.md` first, then inspect the experimental section in `paper_overleaf/neurips.tex`. Treat those files as the current source of truth.

## Mission

Implement and run the experimental campaign infrastructure needed to operationalize the theory in the paper. Focus on moving from preliminary one-step/pilot artifacts to a long-horizon, publication-ready experimental pipeline.

The theory section is not your target. Do not rewrite the theoretical framework. Your work should support the experimental section: long-horizon trajectories, `tau`, survival curves, hazards, routing information, mismatch, decomposition residuals, and final campaign artifacts.

## Autonomy and Iterative Debugging

Work autonomously. Do not stop at the first failing command unless the failure is genuinely unrecoverable. When something fails, debug it iteratively:

1. Read the traceback, logs, config, and relevant source code.
2. Form a concrete hypothesis about the failure.
3. Make the smallest scoped fix that preserves the intended experimental protocol.
4. Re-run the smallest failing smoke test.
5. Repeat until the smoke path passes or the blocker is external, such as missing credentials, model unavailability, rate limits, or a hard API outage.

Prefer continuing with partial but well-documented progress over waiting for human input. If a primary model, task mode, or horizon is blocked, run the largest complete fallback rectangle that is still scientifically meaningful and record the deviation in `OVERNIGHT_STATUS.md`.

You are allowed to create or modify configs, analysis scripts, small helpers, and status reports as needed to complete the overnight mission. Keep changes scoped to the campaign. Do not ask for permission for routine debugging, reruns, config fixes, parser fixes, plotting fixes, or analysis-script fixes.

## Hard Constraints

- Do not delete existing `runs/` or `artifacts/` data.
- Do not treat old preliminary runs as final paper evidence.
- Write new outputs under clearly named final/overnight directories, for example:
  - `runs/final_campaign_overnight_20260430/`
  - `artifacts/final_campaign_overnight_20260430/`
- Keep changes scoped. Do not refactor unrelated code.
- Preserve dirty user files you did not create.
- If API credentials, model access, or rate limits block a run, record the blocker and continue with available smoke or partial runs.
- Respect configured model budgets and timeouts. Do not remove budget guards.
- Log every command you run and every failure you encounter.
- If you make code changes while debugging, run the relevant tests or smoke commands before launching long jobs.

## Required Reading

1. `Next_steps.md`
2. `paper_overleaf/neurips.tex`, especially Section `Operational experimental campaign` and Appendix `Operational estimator details`
3. `configs/models.yaml`
4. Existing campaign configs:
   - `configs/oracle_family_5model_reliable_campaign.yaml`
   - `configs/oracle_family_iterative_multistep.yaml`
   - `configs/oracle_family_iterative_fixed_mode.yaml`
5. Existing analysis modules:
   - `src/vao/analysis/task_mode_decomposition.py`
   - `src/vao/analysis/task_mode_bootstrap.py`
   - `src/vao/analysis/task_mode_robustness.py`
   - `src/vao/analysis/oracle_family_iterative.py`

## Target Model Menu

Primary models for the publication-ready campaign:

- `gpt_5_4_mini`
- `gpt_5_4`
- `gpt_5_3_codex`
- `claude_sonnet`

Optional appendix/fallback models:

- `claude_haiku`
- `claude_opus_4_6`
- `qwen_coder` only if local serving is stable

If one primary model is unavailable, keep the run matrix explicit and continue with available models. Do not silently substitute models without documenting it.

## Campaign Design To Implement

Main setting:

- Horizon: `H=8`
- Short baseline: `H=1`
- Medium diagnostic: `H=3`
- Long stress subset: `H=16`
- Primary observed variable: `tau`, the first step where the verifier certifies success

Publication-ready target from `Next_steps.md`:

- Controlled latent modes: `4 models x 6 modes x 30 tasks`, `H=8`
- Semi-synthetic coding/tool-use: `4 models x 6 modes x 20 tasks`, `H=8`
- Naturalistic agent benchmark: `3 models x 150 tasks`, `H=8`
- Horizon ablation: `4 models x 6 modes x 10 tasks x extra horizons {1,3,16}`, reusing `H=8` subset where valid
- Negative controls: corrupted modes, weak routers, trivial-routing settings

For the overnight run, prioritize in this order:

1. Implement missing logging/analysis required for `tau`, survival curves, hazards, and decomposition residuals.
2. Run smoke tests for all changed code and debug failures until the smoke path is stable.
3. Launch the largest feasible overnight batch using available models and budget.
4. Monitor early outputs long enough to catch obvious configuration or parsing failures; fix and restart if needed.
5. Generate artifacts and reports from whatever completes.
6. Leave a concise status report with completed cells, failed cells, fixes applied, blockers, and next commands.

## Implementation Tasks

### 1. Long-Horizon Trajectory Logging

Ensure every trajectory records:

- `max_horizon`
- per-step verifier success
- per-step scalar loss
- per-step wall time
- per-step token/API cost when available
- cumulative cost to each step
- `tau`, with `null` or `inf` if censored
- stop reason: `success`, `horizon_exhausted`, `parse_error`, `backend_error`, `timeout`, or equivalent

If the current orchestrator already records part of this, add the missing fields without breaking existing analysis scripts.

### 2. Estimators

Implement or verify analysis for:

- `F_hat(M,s,h) = P(tau <= h | M,s)`
- empirical survival `S_hat(M,s,h)`
- empirical hazard `lambda_hat(M,s,h)`
- cumulative cost to `tau wedge h`
- long-horizon score `rho_H(M,s) = -log F_hat(M,s,H) + log C_hat(M,s,H)`
- geometric surrogate check against `1 - (1 - p_hat(M,s))^h`
- decomposition residual: observed log effort minus predicted score
- bootstrap intervals by model-mode cell
- Wilson intervals for success probabilities

Create a new analysis module if appropriate, for example:

`src/vao/analysis/long_horizon_estimators.py`

and corresponding artifacts under:

`artifacts/final_campaign_overnight_20260430/`

### 3. Routers

Implement or verify at least these router policies:

- single-model baseline
- oracle-mode router
- learned metadata router if features are available
- weak/noisy router negative control

If learned trace routing is too large for tonight, prepare the interface and report it as pending.

### 4. Configs

Create clean overnight configs rather than mutating old pilot configs destructively. Suggested names:

- `configs/final_campaign_controlled_overnight.yaml`
- `configs/final_campaign_horizon_ablation_overnight.yaml`
- `configs/final_campaign_negative_controls_overnight.yaml`

Use explicit run roots and artifact roots containing `final_campaign_overnight_20260430`.

### 5. Run Plan

Run in this order:

1. Local/stub smoke to verify logging and analysis.
2. One small real-model smoke with `H=2` or `H=3`.
3. Controlled latent-mode batch with `H=8`.
4. Horizon ablation subset with `H in {1,3,16}`.
5. Negative controls if time remains.

If the full 4-model campaign is not feasible overnight, run the largest complete rectangular subset possible. Prefer a complete model-mode-task rectangle over scattered partial cells.

If an overnight batch fails partway through, do not abandon the campaign. Inspect the first failing run, fix the root cause when possible, resume from completed cells, and document which cells were skipped or retried.

## Required Outputs

At the end, write:

`artifacts/final_campaign_overnight_20260430/OVERNIGHT_STATUS.md`

It must include:

- git commit hash used
- configs used
- commands executed
- debugging fixes applied
- models attempted
- task modes attempted
- horizons attempted
- number of completed trajectories
- number of completed model-step calls
- failures by category
- generated artifact paths
- plots/reports generated
- blockers
- recommended next commands

Also produce machine-readable summaries where possible:

- `trajectory_summary.csv`
- `survival_by_model_mode.csv`
- `hazard_by_model_mode.csv`
- `cost_by_model_mode.csv`
- `decomposition_residuals.csv`
- `router_comparison.csv`
- `bootstrap_summary.json`

## Paper Alignment

After generating results, do not fill numerical results into the paper unless the campaign is complete enough to be publication-ready. Instead, write a short note explaining which placeholders in `paper_overleaf/neurips.tex` can eventually be filled by which artifact files.

## Final Response

When finished, report:

1. What was implemented.
2. What ran successfully.
3. What failed and why.
4. Whether the campaign is ready to promote any paper claim.
5. The exact next commands for continuing the campaign.
