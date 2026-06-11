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

## Current Milestone

Phase F commit.

## Open Questions

- Concrete production model strings and credentials are not needed for the
  deterministic smoke path. Full LLM-backed SELECT/ADAPT/IMPLEMENT and live
  solving will require operator-provided model routing or environment variables.
- Production Phase F is blocked on real model-backed completions or a concrete
  model adapter configuration. Return at:
  1. `python -m runners.seed_solve --completion-jsonl step1/logs/seed_solver_completions.jsonl`
  2. `python -m runners.online_loop --completion-jsonl step1/logs/cheap_node_completions.jsonl`
  3. `python -m metrics.compute_step1`

## Full-Run Command For Operator

Do not run this during implementation:

```bash
source .venv/bin/activate
export PYTHONPATH=step1:.

python -m runners.profile
python -m runners.self_discover --profile step1/profile/task_profile.json
python -m runners.routing --profile step1/profile/task_profile.json --output step1/artifact/routing_calibration.json
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
python -m runners.seed_solve \
  --completion-jsonl step1/logs/seed_solver_completions.jsonl \
  --output step1/logs/seed_solve_traces.jsonl
python -m runners.online_loop \
  --completion-jsonl step1/logs/cheap_node_completions.jsonl \
  --orchestration-output step1/logs/online_loop_traces.jsonl \
  --baseline-output step1/logs/baseline_traces.jsonl
python -m metrics.compute_step1
```
