# Step 1 Progress

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
    because `NODE_MODEL`, `OPENAI_API_KEY`, and `OPENAI_BASE_URL` are unset.
  - `seed_solve --limit 3 --allow-mock` and
    `online_loop --limit 3 --allow-mock` still work for dev-only smoke.
  - `online_loop --limit 3` without a completion file fails loudly.
  - `online_loop --limit 3 --completion-jsonl /tmp/completions_3.jsonl`
    completed with `mock_default_count=0`.
- Task-0 per-node exercise audit completed before any model calls.
  - Current completion contract is still one `{task_id, completion}` row per
    instance.
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
  - Minimal proposed fix, not yet implemented: extend the generator output to a
    per-instance record with node-specific fields, for example
    `{task_id, spec_struct, plan_struct, test_suite, completion,
    repaired_completion, selected_completion, node_usage}`. Keep backward
    compatibility by accepting legacy `{task_id, completion}` only for
    baseline/final-code smoke, but require the richer record for Phase-F
    per-node attribution. Then `run_orchestration_instance` should consume
    those fields as `s_k`, run each `check_k` on its own handoff, and populate
    `T_k` from `node_usage` rather than synthetic wall time.
- Per-node contract implemented after operator continuation.
  - JSONL remains one row per instance.
  - Required production schema:
    `{task_id, understand_spec, plan, generate_tests, implement, repair,
    node_usage}`.
  - `understand_spec` is the model-produced `spec_struct`.
  - `plan` is the model-produced `plan_struct`.
  - `generate_tests` is the model-produced `test_suite` with `tests` and
    `rationale`.
  - `implement` is an object with at least `{completion, notes}`.
  - `repair` is an object with at least `{completion, repair_summary}`.
  - `node_usage` maps each model node to `{calls, tokens_in, tokens_out,
    total_tokens, wall_ms, model, reasoning_effort, transport}` and is used for
    `T_k`.
  - `run_orchestration_instance` now feeds each node its own state:
    `check_understand_spec` sees the model `understand_spec`, `check_generate_tests`
    sees model tests run on the implement completion, `check_implement` sees the
    implement completion, and `check_repair` sees the repair completion.
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
  - Synthetic per-node record validation passed with 3 covered ids and
    `mock_default_count=0`.
  - `metrics.compute_step1` now reports offline gold-diagnostic agreement for
    nodes with `check_*_gold` diagnostics (`understand_spec`,
    `generate_tests`).
- Real mini-smoke remains blocked before model calls because `SEED_MODEL` and
  `NODE_MODEL` are unset in this shell. `generate_completions --role seed`
  stops with: `Missing model configuration: set SEED_MODEL or pass --config
  with seed_model.`

## Current Milestone

Blocked before real mini-smoke on missing Codex-suite model ids.

## Open Questions

- Concrete production model strings and credentials are not needed for the
  deterministic smoke path. Full LLM-backed SELECT/ADAPT/IMPLEMENT and live
  solving will require operator-provided model routing or environment variables.
- Production Phase F is blocked on real model-backed completions or a concrete
  model adapter configuration. Return at:
  1. `python -m runners.seed_solve --completion-jsonl step1/logs/seed_solver_completions.jsonl`
  2. `python -m runners.online_loop --completion-jsonl step1/logs/cheap_node_completions.jsonl`
  3. `python -m metrics.compute_step1`
- Real mini-smoke is blocked until the operator provides:
  - `SEED_MODEL`
  - `NODE_MODEL`
  - optional: `SEED_REASONING_EFFORT`, `NODE_REASONING_EFFORT`,
    `CODEX_TIMEOUT_SECONDS`, `CODEX_SANDBOX`

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

python -m runners.generate_completions \
  --role cheap \
  --instances step1/data/humaneval_public_smoke_stratified.jsonl \
  --output step1/logs/cheap_node_completions_smoke.jsonl

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
python -m runners.generate_completions \
  --role cheap \
  --output step1/logs/cheap_node_completions.jsonl
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
python -m runners.generate_completions \
  --role cheap \
  --output step1/logs/cheap_node_completions.jsonl
python -m runners.seed_solve \
  --completion-jsonl step1/logs/seed_solver_completions.jsonl \
  --output step1/logs/seed_solve_traces.jsonl
python -m runners.online_loop \
  --completion-jsonl step1/logs/cheap_node_completions.jsonl \
  --orchestration-output step1/logs/online_loop_traces.jsonl \
  --baseline-output step1/logs/baseline_traces.jsonl
python -m metrics.compute_step1
```
