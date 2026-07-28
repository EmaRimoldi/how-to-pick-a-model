# Step 1 Progress

## Recovery Report - 2026-06-11 rep42

Source of truth checked: `swebench/step_1_induction/PLAN.md`.

Requested git state:
- Latest commit from `git log --oneline -10`: `6113410 Record HumanEval real mini smoke`.
- `git status --short step1`: `M step1/metrics/compute_step1.py`.
- The rep42 data/log files are present but ignored scratch artifacts, not shown by the default
  Step 1 status. `git status --short --ignored step1` shows the rep42 `step1/data` files and
  `step1/logs/` as ignored.

Coverage from disk, validated with `.venv` via `uv run --no-sync` and
`runners.validate_node_records`:
- Seed records: 42/42. Inputs:
  `step1/logs/seed_solver_completions_smoke.jsonl` plus
  `step1/logs/seed_solver_completions_rep42_missing.jsonl`. Validation passed, real
  `node_usage` present, distinct handoffs passed, `mock_default_count=0`.
- Node records: 9/42. Input:
  `step1/logs/cheap_node_completions_smoke.jsonl`. Validation passed for those 9 records, real
  `node_usage` present, distinct handoffs passed, `mock_default_count=0`.
- Missing seed task_ids: none.
- Missing node task_ids:
  `HumanEval/4`, `HumanEval/5`, `HumanEval/6`, `HumanEval/7`, `HumanEval/8`, `HumanEval/9`,
  `HumanEval/10`, `HumanEval/11`, `HumanEval/12`, `HumanEval/13`, `HumanEval/14`,
  `HumanEval/15`, `HumanEval/16`, `HumanEval/17`, `HumanEval/18`, `HumanEval/19`,
  `HumanEval/21`, `HumanEval/22`, `HumanEval/23`, `HumanEval/24`, `HumanEval/25`,
  `HumanEval/26`, `HumanEval/27`, `HumanEval/40`, `HumanEval/43`, `HumanEval/52`,
  `HumanEval/58`, `HumanEval/67`, `HumanEval/68`, `HumanEval/69`, `HumanEval/71`,
  `HumanEval/72`, `HumanEval/73`.

Diagnostics status:
- Full rep42 deterministic diagnostics were not run because cheap-node coverage is partial
  (9/42). No model generation, no 164-run, and no SLURM job were run during recovery.
- Metrics patch status: present only in the working tree (`M step1/metrics/compute_step1.py`),
  not committed. The patch contains offline `tau_bar`, `Fbar(t)`, `Fbar(inf)`, and
  `utility_c_sweep`; `PYTHONPATH=step1:. uv run --no-sync python -m py_compile
  step1/metrics/compute_step1.py` passed.
- Results table: not available because diagnostics did not run.

Exact resume command for missing records only:

```bash
PYTHONPATH=step1:. NODE_MODEL=gpt-5.4-mini NODE_REASONING_EFFORT=low uv run --no-sync python -m runners.generate_completions \
  --role cheap \
  --instances step1/data/humaneval_public_smoke_rep42_missing_cheap.jsonl \
  --output step1/logs/cheap_node_completions_rep42_missing.jsonl
```

Source of truth: `swebench/step_1_induction/PLAN.md`. The prompt requested a
co-located `PLAN.md`; none exists at the repository root, but this file contains
the HumanEval Step 1 plan and governs the implementation.

## Done

- Verified requested arXiv identifiers:
  - FlowMind: `2602.11782`
  - TDAG: `2402.10178`
- Activated the existing project `.venv`.
- Scaffolded `step1/{data,blocks,profile,artifact,oracles,runners,logs,metrics,prompts}`.
- Phase A: created `blocks/library.yaml` with typed orchestration operators,
  I/O contracts, model tier policies, valid edges, default routing paths, and
  `U(h) = R * pass - c * sum(T_k)` accounting.
- Phase A validation passed: 9 required operators and 13 valid edges parsed.
- Phase B: implemented `runners/profile.py` and generated
  `profile/task_profile.json` over HumanEval-164 using prompt-only features.
- Phase B validation passed:
  - smoke profile on 3 instances completed with `canonical_solution_used=false`
  - full prompt-only profile completed with 164 instances
  - full profile clusters: easy=108, medium=49, hard=7
  - `step1/data/humaneval_public.jsonl` and
    `step1/data/humaneval_verifier.jsonl` contain 164 rows each and no
    canonical-solution content
- Phase C: implemented `runners/self_discover.py`, wrote
  `artifact/dag_candidate.json`, `artifact/orchestration.md`, and role prompts.
- Phase C validation passed: DAG JSON parses, Markdown YAML parses, all selected
  edges are in the Phase-A library, and utility notation is preserved as
  `U(h) = R·1[pass] − c·T(h), T(h) = Σ T_k`.
- Phase D: implemented sandboxed execution, seed-solve runner, online-loop
  runner, deterministic workflow helpers, inference oracles, diagnostic gold
  oracles where applicable, and AWM/oracle-synthesis prompts.
- Phase D validation passed:
  - sandbox positive check: HumanEval/0 canonical completion passes public
    examples and terminal verifier
  - sandbox negative check: dummy completion fails terminal verifier
  - seed-solve smoke on 3 instances completed and wrote raw traces
  - online-loop smoke on 3 instances completed and wrote raw traces
  - generated-test inference oracle accepts a correct candidate and rejects a
    dummy candidate; gold diagnostic accepts the canonical solution offline
- Phase E: implemented `runners/routing.py`, regenerated
  `artifact/orchestration.md` with DAAO thresholds and TDAG expansion policy,
  and wrote `artifact/routing_calibration.json`.
- Phase E validation passed:
  - routing decision counts match profile clusters: easy=108, medium=49,
    hard=7
  - calibrated repair budgets are easy=0, medium=1, hard=2
  - artifact routing YAML parses and contains the TDAG error-propagation policy
- Phase F: implemented `metrics/compute_step1.py`, regenerated the default
  three-instance smoke logs, and wrote `metrics/step1_report.json` plus
  `metrics/adaptation_curve.json`.
- Phase F smoke validation:
  - structural validity passed
  - inference-oracle discrimination failed on the mock-completion smoke run
    (`inference_oracle_discriminating_fraction=0.0`)
  - `E[U]` did not beat the single-agent baseline on the mock-completion smoke
    run (`orchestration_mean_U=-1.292e-05`,
    `baseline_mean_U=-1.0926666666666667e-05`)
  - this is expected for dummy completions; production Phase F must resume after
    real cheap-node and seed-solver completions/model routing are available
- Continuation: confirmed the runner completion contract in
  `runners/workflow.py`.
  - JSONL schema is one object per line.
  - Required keys: `task_id: str`, `completion: str`.
  - `completion` is a single HumanEval function-body continuation string to
    append directly after `prompt`; it is not a per-node dictionary.
  - Extra keys such as `role`, `model`, `usage`, and `raw_completion` are
    allowed and ignored by `load_completion_map`.
- Continuation: added `runners/generate_completions.py`.
  - This is the only Step-1 file that performs model/API access.
  - It reads public instances from `step1/data/humaneval_public.jsonl`.
  - It asserts public solving inputs do not contain `test` or
    `canonical_solution`.
  - It resolves model/backend settings from environment variables or an
    optional JSON/YAML config; no model strings or credentials are hardcoded.
- Continuation: enforced production coverage/no-mock guards.
  - `seed_solve` and `online_loop` now default to public instances and take
    verifier tests separately via `--verifier-instances`.
  - Missing completion coverage now fails unless `--allow-mock` is explicitly
    passed for development.
  - Runner summaries report `mock_default_count`; production runs must be zero.
- Continuation guard validation:
  - `generate_completions --role cheap --limit 1` stopped before API access
    because `NODE_MODEL` is unset.
  - `seed_solve --limit 3 --allow-mock` and
    `online_loop --limit 3 --allow-mock` still work for dev-only smoke.
  - `online_loop --limit 3` without a completion file fails loudly.
  - `online_loop --limit 3 --completion-jsonl /tmp/completions_3.jsonl`
    completed with `mock_default_count=0`.
- Task-0 per-node exercise audit completed before any model calls.
  - Historical finding at commit `f27678e`: the completion contract was one
    `{task_id, completion}` row per instance.
  - Nodes do not all literally receive the same state, but all model-produced
    behavior collapses to the single final `completion` string. `route`,
    `understand_spec`, `plan`, and `generate_tests` receive deterministic
    prompt/profile-derived states, not model-generated handoffs. `implement`
    receives the final completion. `repair` receives the same final completion;
    no repaired code is generated. `aggregate` selects the same only candidate.
  - Node audit:
    - `route`: state is `{"route_decision": route_from_feature(profile)}`.
      `check_route` verifies difficulty and path are allowed. `T_k` is
      wall-clock time in `_trace`; tokens are zero, calls are zero.
    - `understand_spec`: state is `{"spec_struct": spec_from_prompt(...)}`.
      `check_understand_spec` verifies prompt signature/example consistency.
      `T_k` is wall-clock plus synthetic `calls=1`; token counts are zero.
    - `plan`: state is `{"plan_struct": plan_from_spec(spec)}`. There is no
      executable `check_plan`; the trace stores a rubric placeholder
      `{"passed": None, "kind": "rubric"}`. `T_k` is wall-clock plus
      synthetic `calls=1`; token counts are zero.
    - `generate_tests`: state is prompt-derived doctest assertions from
      `generated_tests_from_prompt`. `check_generate_tests` inspects those
      tests and runs them on the final `completion`; it does not inspect a
      model-generated test artifact. `T_k` is wall-clock plus synthetic
      `calls=1`; token counts are zero.
    - `implement`: state records only `completion_chars`; `check_implement`
      runs the final `completion` on public examples. `T_k` is wall-clock plus
      synthetic `calls=1`; token counts are zero.
    - `run_tests`: state records public/generated/terminal pass booleans.
      There is no local oracle; terminal verifier is the check. `T_k` is
      wall-clock plus `verifier_calls=1`.
    - `repair`: state records the same final completion length and a mock
      repair summary. `check_repair` runs the same final `completion` on public
      examples and generated tests. `T_k` is wall-clock plus synthetic
      `calls=1`; token counts are zero.
    - `aggregate`: state records selected completion length and
      `selection_reason="only candidate"`. There is no local oracle. `T_k` is
      wall-clock only.
  - Diagnosis: per-node oracle discrimination and per-node cost attribution are
    structurally weak under the single-completion contract. A real mini-smoke
    would measure final-code quality, not distinct per-node handoff quality.
  - Minimal proposed fix, since approved and implemented: extend the generator
    output to a per-instance record with node-specific fields:
    `{task_id, spec_struct, plan_struct, test_suite, completion,
    repaired_completion, selected_completion, node_usage}`. Phase-F runners now
    require the richer record for per-node attribution. `run_orchestration_instance`
    consumes those fields as `s_k`, runs each `check_k` on its own handoff, and
    populates `T_k` from `node_usage` rather than synthetic model placeholders.
- Per-node contract implemented after operator continuation.
  - JSONL remains one row per instance.
  - Required production schema:
    `{task_id, spec_struct, plan_struct, test_suite, completion,
    repaired_completion, selected_completion, node_usage}`.
  - `spec_struct` is the model-produced `understand_spec` node output.
  - `plan_struct` is the model-produced `plan` node output.
  - `test_suite` is the model-produced `generate_tests` node output with
    `tests` and `rationale`.
  - `completion` is the model-produced `implement` node output.
  - `repaired_completion` is the model-produced `repair` node output.
  - `selected_completion` is the completion selected by the aggregate step.
  - `node_usage` maps each model node to `{prompt_tokens,
    completion_tokens, calls, wall_ms}` plus optional `total_tokens`, `model`,
    `reasoning_effort`, `transport`, and token split provenance. Model-node
    `T_k` is computed from the recorded tokens, real call count, and real wall
    time; deterministic nodes report `calls=0` and real wall time.
  - `run_orchestration_instance` now feeds each node its own state:
    `check_understand_spec` sees `spec_struct`, `check_generate_tests` sees
    `test_suite` run on `completion`, `check_implement` sees `completion`, and
    `check_repair` sees `repaired_completion`.
  - `seed_solve` and `online_loop` now load per-node records via
    `load_node_record_map`; flat `{task_id, completion}` rows are no longer the
    production contract.
- Codex-suite backend implemented.
  - `runners/generate_completions.py` now uses the local `codex exec` transport
    via `CodexCliAdapter`; no paid HTTP API client is used.
  - Model identifiers are resolved only from env/config:
    `SEED_MODEL` for `--role seed`, `NODE_MODEL` for `--role cheap`.
  - Optional controls: `SEED_REASONING_EFFORT`, `NODE_REASONING_EFFORT`,
    `CODEX_TIMEOUT_SECONDS`, `CODEX_SANDBOX`, or matching config keys.
  - The local CLI is present: `codex-cli 0.137.0`.
- Stratified mini-smoke support implemented:
  - `runners/select_subset.py --limit 9` writes leakage-safe public/verifier
    subset files.
  - `runners/validate_node_records.py` checks coverage, distinct handoff
    states, unchanged-repair status, and non-placeholder `node_usage`.
  - Synthetic per-node record validation passed with 3 covered ids and
    `mock_default_count=0`.
  - `metrics.compute_step1` now reports offline gold-diagnostic agreement for
    nodes with `check_*_gold` diagnostics (`understand_spec`,
    `generate_tests`).
- Approved-schema validation:
  - Synthetic records with
    `{task_id, spec_struct, plan_struct, test_suite, completion,
    repaired_completion, selected_completion, node_usage}` load successfully.
  - `online_loop --limit 3 --completion-jsonl /tmp/approved_node_records_3.jsonl`
    completed with `mock_default_count=0`.
  - After replacing model-node call placeholders with real `node_usage.calls`,
    `metrics.compute_step1` on the synthetic traces reported per-node cost
    summaries and non-zero oracle discrimination
    (`inference_oracle_discriminating_fraction=0.125`) for the fixture,
    confirming the plumbing can observe distinct handoff states. This is not a
    production model signal.
  - `runners.validate_node_records --records /tmp/approved_node_records_3.jsonl`
    passed.
- Diagnostic Check 3 resolved:
  - Rephrased the generator hard-rule prompt to forbid reference/ground-truth
    solutions without naming the dataset gold field.
  - On `HumanEval/0` and `HumanEval/1`, the generated base context is unchanged
    except for that negative-rule wording.
  - `rg -n "canonical_solution" step1/runners/generate_completions.py` now
    returns no hits; remaining literal mentions are guards, offline diagnostics,
    metadata/profiling reports, and documentation.
- Codex-suite invocation status:
  - Local CLI is callable through `CodexCliAdapter`.
  - Used shared model IDs from `configs/models.yaml`: `SEED_MODEL=gpt-5.5`
    with `SEED_REASONING_EFFORT=xhigh`, and `NODE_MODEL=gpt-5.4-mini` with
    `NODE_REASONING_EFFORT=low`.
  - Cheap one-instance handshake on `HumanEval/0` succeeded and
    `runners.validate_node_records` passed. The generated record had distinct
    `completion` and `repaired_completion`, `repair_status=model_repair_output`,
    and real Codex usage on all model nodes.
  - Codex CLI usage for that handshake exposed total tokens only; `T_k` is real,
    but prompt/completion split provenance is `codex_total_only`, so
    `completion_tokens` is `0` in the current record.
  - Seed one-instance handshakes on `HumanEval/0` invoked `gpt-5.5` successfully
    but failed the repair contract after one and then two bounded retries:
    `ValueError: Repair node returned an unchanged completion for failing
    candidate 'HumanEval/0'`.
  - Tightened the repair prompt to state that identical output is allowed only
    when the candidate passes all provided feedback. A final one-instance seed
    handshake still failed with the same unchanged-failing-repair error.
  - No 8-10 instance mini-smoke, 164-instance run, or SLURM job was launched.
- Seed repair diagnosis:
  - Scope stayed within `HumanEval/0`, `HumanEval/1`, and `HumanEval/2`.
  - `HumanEval/0` is a valid repair exercise in the failing seed diagnostic:
    the implement node produced an over-indented body, and both public and
    generated self-tests failed with `IndentationError: unexpected indent`.
  - The exact raw repair response from `gpt-5.5` contained a corrected body and
    repair summary. Replaying the raw body directly passes both public examples
    and generated self-tests.
  - Root cause was parsing/normalization, not model behavior:
    `_strip_code_fence()` used `text.strip()`, which removed the first line's
    leading indentation from an unfenced function body. `normalize_completion()`
    then indented the whole block and recreated the failing over-indented body.
  - Fix: preserve leading indentation for unfenced completions and only strip
    indentation-insensitive wrapper text when removing an actual Markdown code
    fence. Also avoid consuming first-line indentation after a fence header.
  - Before/after replay on the saved `HumanEval/0` raw repair:
    before normalization produced indent levels `[4, 8, 12, 16, 8]` and failed;
    after the fix it produces `[4, 4, 8, 12, 4]` and passes both public and
    generated self-tests.
  - End-to-end seed generation for `HumanEval/0` after the parser fix completed
    and `runners.validate_node_records` passed. In that later sample the
    implement node already passed self-tests, so unchanged repair was correctly
    logged as `repair_status=unchanged_candidate_passed_self_tests`.
  - `HumanEval/1` and `HumanEval/2` also had implement completions that passed
    public/generated self-tests, so they did not exercise repair; unchanged
    repair was the correct no-op for both. Diagnostic logs were written under
    `step1/logs/seed_repair_diagnostic_*.json`.
  - Hold point: repair is verified for the observed true failing raw response,
    but the requested 8-10 instance mini-smoke has not been started.
- First real per-node mini-smoke completed on 9 stratified instances:
  - Subset ids: `HumanEval/0`, `HumanEval/1`, `HumanEval/2`,
    `HumanEval/3`, `HumanEval/20`, `HumanEval/32`, `HumanEval/109`,
    `HumanEval/115`, `HumanEval/127` (3 easy, 3 medium, 3 hard via
    `task_profile.json`).
  - Added `.gitignore` entries for reproducible smoke subset files under
    `step1/data/`.
  - Verified the shared normalizer fix on `implement` outputs from
    `HumanEval/0-2`; normalization did not corrupt valid implement bodies.
    Verdicts after replay were unchanged: `HumanEval/0` implement still failed
    due to its own over-indent, while `HumanEval/1` and `HumanEval/2` remained
    passing.
  - Generated real per-node seed records with `SEED_MODEL=gpt-5.5`,
    `SEED_REASONING_EFFORT=xhigh`: 9/9 records validated; `seed_solve` passed
    9/9 with `mock_default_count=0`.
  - Generated real per-node cheap/node records with `NODE_MODEL=gpt-5.4-mini`,
    `NODE_REASONING_EFFORT=low`: 9/9 records validated; online loop completed
    with `mock_default_count=0`.
  - Cheap record repair statuses: 5 unchanged no-op repairs where implement
    already passed, 4 model repair outputs
    (`HumanEval/2`, `HumanEval/32`, `HumanEval/115`, `HumanEval/127`).
  - Online orchestration pass@1: 9/9 = 1.0. Single-agent baseline pass@1:
    8/9 = 0.8888888889. The orchestration rescued `HumanEval/127`, where the
    baseline failed.
  - Utility result: orchestration mean `E[U]=0.4447390867`; baseline mean
    `E[U]=0.67630531`. Phase-F utility check is not passed because extra node
    cost dominates the one additional solved instance on this subset.
  - Inference oracle discrimination: `inference_oracle_discriminating_fraction=0.25`;
    Case-1 code-oracle fraction `0.4`. Discriminating nodes:
    `understand_spec` and `generate_tests`. Non-discriminating observed nodes:
    `route` (always true), `implement` (all cheap implementations passed public
    examples), `repair` (only one routed repair trace and it failed generated
    self-tests), plus `plan` is rubric-only and `run_tests`/`aggregate` are
    terminal/opaque by design.
  - Gold diagnostic agreement: `understand_spec=1.0` over 9 observations;
    `generate_tests=1.0` over 3 observations; no gold diagnostic
    disagreements were observed.
  - Cost concentration in the online traces by total `T_k`: `implement`
    38.28%, `understand_spec` 27.93%, `plan` 18.96%,
    `generate_tests` 9.95%, `repair` 4.88%, deterministic nodes negligible.
    Codex CLI exposed total tokens only (`token_split_source=codex_total_only`),
    so `prompt_tokens` carries the total and `completion_tokens=0`; `T_k` still
    uses real total tokens, calls, and wall time.
  - Metrics written to both smoke-specific and default files:
    `step1/metrics/step1_report_smoke_real.json`,
    `step1/metrics/adaptation_curve_smoke_real.json`,
    `step1/metrics/step1_report.json`,
    `step1/metrics/adaptation_curve.json`.
  - Decision: discrimination is low but non-zero, gold agreement is clean, and
    pass@1 improves, but the orchestration is not ready for the full 164-run
    because it does not beat the single-agent baseline on `E[U]` under the
    current cost model.

## Current Milestone

Hold after the first real 9-instance per-node mini-smoke. No full 164-instance
loop was run and no SLURM job was submitted. Next work should reduce cost or
routing breadth before launching the full run.

## Open Questions

- Concrete production model strings can be supplied through env/config. The
  diagnostic handshakes used `gpt-5.5` and `gpt-5.4-mini` from the shared repo
  model config.
- Production Phase F is blocked on real model-backed completions or a concrete
  model adapter configuration. Return at:
  1. `python -m runners.seed_solve --completion-jsonl step1/logs/seed_solver_completions.jsonl`
  2. `python -m runners.online_loop --completion-jsonl step1/logs/cheap_node_completions.jsonl`
  3. `python -m metrics.compute_step1`
- Full run should wait until the cost/routing issue is addressed. The current
  mini-smoke improves pass@1 but loses on expected utility.

## Real Mini-Smoke Command

Run after setting Codex-suite model environment variables:

```bash
source .venv/bin/activate
export PYTHONPATH=step1:.

python -m runners.select_subset \
  --limit 9 \
  --public-output step1/data/humaneval_public_smoke_stratified.jsonl \
  --verifier-output step1/data/humaneval_verifier_smoke_stratified.jsonl \
  --ids-output step1/data/humaneval_smoke_stratified_ids.json

python -m runners.generate_completions \
  --role seed \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --output step1/logs/seed_solver_completions_smoke.jsonl

python -m runners.validate_node_records \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --records step1/logs/seed_solver_completions_smoke.jsonl

python -m runners.generate_completions \
  --role cheap \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --output step1/logs/cheap_node_completions_smoke.jsonl

python -m runners.validate_node_records \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --records step1/logs/cheap_node_completions_smoke.jsonl

python -m runners.seed_solve \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --verifier-instances step1/data/humaneval_verifier_smoke_stratified.jsonl \
  --completion-jsonl step1/logs/seed_solver_completions_smoke.jsonl \
  --output step1/logs/seed_solve_smoke_real.jsonl

python -m runners.online_loop \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --verifier-instances step1/data/humaneval_verifier_smoke_stratified.jsonl \
  --completion-jsonl step1/logs/cheap_node_completions_smoke.jsonl \
  --orchestration-output step1/logs/online_loop_smoke_real.jsonl \
  --baseline-output step1/logs/baseline_smoke_real.jsonl

python -m metrics.compute_step1 \
  --orchestration-traces step1/logs/online_loop_smoke_real.jsonl \
  --baseline-traces step1/logs/baseline_smoke_real.jsonl \
  --report-output step1/metrics/step1_report_smoke_real.json \
  --curve-output step1/metrics/adaptation_curve_smoke_real.json
```

## Full-Run Command For Operator

Do not run this during implementation:

```bash
source .venv/bin/activate
export PYTHONPATH=step1:.

python -m runners.profile
python -m runners.self_discover --profile step1/profile/task_profile.json
python -m runners.routing --profile step1/profile/task_profile.json --output step1/artifact/routing_calibration.json
python -m runners.generate_completions \
  --role seed \
  --output step1/logs/seed_solver_completions.jsonl
python -m runners.validate_node_records \
  --records step1/logs/seed_solver_completions.jsonl
python -m runners.generate_completions \
  --role cheap \
  --output step1/logs/cheap_node_completions.jsonl
python -m runners.validate_node_records \
  --records step1/logs/cheap_node_completions.jsonl
python -m runners.seed_solve \
  --completion-jsonl step1/logs/seed_solver_completions.jsonl \
  --output step1/logs/seed_solve_traces.jsonl
python -m runners.online_loop \
  --completion-jsonl step1/logs/cheap_node_completions.jsonl \
  --orchestration-output step1/logs/online_loop_traces.jsonl \
  --baseline-output step1/logs/baseline_traces.jsonl
python -m metrics.compute_step1
```

SLURM template:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=humaneval-step1
#SBATCH --output=step1/logs/slurm-%j.out
#SBATCH --error=step1/logs/slurm-%j.err
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail
cd /home/erimoldi/openclaw_remote/projects/NeurIPS_2026
source .venv/bin/activate
export PYTHONPATH=step1:.

python -m runners.profile
python -m runners.self_discover --profile step1/profile/task_profile.json
python -m runners.routing --profile step1/profile/task_profile.json --output step1/artifact/routing_calibration.json
python -m runners.generate_completions \
  --role seed \
  --output step1/logs/seed_solver_completions.jsonl
python -m runners.validate_node_records \
  --records step1/logs/seed_solver_completions.jsonl
python -m runners.generate_completions \
  --role cheap \
  --output step1/logs/cheap_node_completions.jsonl
python -m runners.validate_node_records \
  --records step1/logs/cheap_node_completions.jsonl
python -m runners.seed_solve \
  --completion-jsonl step1/logs/seed_solver_completions.jsonl \
  --output step1/logs/seed_solve_traces.jsonl
python -m runners.online_loop \
  --completion-jsonl step1/logs/cheap_node_completions.jsonl \
  --orchestration-output step1/logs/online_loop_traces.jsonl \
  --baseline-output step1/logs/baseline_traces.jsonl
python -m metrics.compute_step1
```
