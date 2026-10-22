# How to Pick a Model

**After a failed attempt, should an agent reuse its work or start again?**

We study whether code and verifier feedback from a failed attempt help the next
attempt, and whether that benefit can be predicted before paying for it. The
longer-term goal is cost-aware continue/restart/switch/stop decisions for agents.

This repository retains the AutoResearch/CIFAR-10 and HumanEval+ evidence needed
to study that question: verified trajectories, retry-allocation baselines,
context/routing experiments, cost accounting, and reproducible figures.

**Latest result:** an [audited producer-transfer experiment](experiments/humaneval-plus/context-value/results/validation-20261022/report.md)
contains **1,353 model responses, 83 development tasks and 60 evaluation tasks**.
On 25 evaluation failures, 9B fresh recovery succeeds 66% of the time versus 50%
with failed code alone. In budgeted replay, the state selector solves 55/60 whole tasks, matching the
stronger development-selected static rule; its utility advantage over that rule
has an interval spanning zero. Reliable prediction of context benefit remains
unproven. Read the [blog draft](docs/blog/when-to-keep-failed-code.md) for results,
costs, controls and the closest prior work.

The policy was trained on Gemma failures and evaluated on Ministral failures
after Gemma's upstream pool became unavailable. This is a declared transfer test;
the original same-producer validation is not complete. Simple one-checkpoint
selectors and replay are implemented. A general multi-step controller remains
future work. Historical traces cannot score an unobserved handoff.

![Recovery outcomes, policy costs and prediction errors on the frozen task holdout](experiments/humaneval-plus/context-value/results/validation-20261022/validation.png)

Start with the [decision protocol](docs/decision-protocol.md), the
[experiment index](experiments/README.md), and the
[reproduction guide](docs/reproducibility.md).

## What is retained

- **AutoResearch/CIFAR-10:** starting-model calibration, controlled evaluation,
  shared-memory ablation, and three-worker routing/first-hit accounting.
- **HumanEval+:** model-size frontier, retry allocation, strategy routing,
  and held-out router-context search.
- **Runtime:** existing edit/verify execution, session handling, snapshots,
  token/cost records, and the historical `agent-workflow` baseline CLI.
- **Manuscripts:** the two existing paper sources and consolidated theory,
  with only their referenced figures vendored under `paper/`.

## Quick start

Recompute the audited results from recorded outputs, without credentials, model
calls, candidate execution or GPUs:

```bash
uv sync --dev --frozen
uv run python scripts/analyze_recovery_validation.py \
  --input experiments/humaneval-plus/context-value/results/validation-20261022 \
  --output runs/recovery-reanalysis
```

Use a fresh output directory. Historical LFS archives are unnecessary for this
analysis; new clones can use
`GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/EmaRimoldi/how-to-pick-a-model.git`.
The saved data include forecasts, frozen weights, task-level replays, receipts,
and six unresolved admissions held at their full reservation. Known charges plus
all reservations and the prior discovery total **$0.5149634**, below the $2 cap.

Repository checks and the historical fixture demo:

```bash
uv sync --dev --frozen
make check
uv run agent-workflow demo --experiment-id readme_demo
```

The demo generates fixture reports locally. It uses no live models or GPUs and
is not an empirical result. See [demo instructions](docs/demo.md).

Regenerate three AutoResearch figures from tracked processed evidence:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed   --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json   --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Live runs require explicit model/compute setup. Optional environments and safe
commands are documented in [reproducibility](docs/reproducibility.md).

## Repository map

| Path | Role |
| --- | --- |
| `experiments/` | Eight baseline bundles, a continuation pilot, context diagnostics and frozen transfer evidence |
| `autoresearch/` | CIFAR-10 benchmark, verification, accounting, and analysis |
| `src/vao/` | Verified execution and model adapters |
| `src/agent_workflow/` | Baseline CLI, instrumentation, and reporting |
| `src/*.py` | HumanEval+ traces, retries, routing, and analyses |
| `paper/` | Existing manuscripts, theory anchor, and referenced figures |
| `artifacts/raw/` | Raw campaign archives in Git LFS |
| `docs/` | Decision protocol, evidence boundaries, reproduction, and source maps |

## Evidence limits

The three-worker AutoResearch panel has 270 processed trajectories and 180
available balanced raw traces. HumanEval+ retains worker logs for 164 tasks per
model. These results describe their recorded protocols; changing actions or
passing context between models requires new measurements.

The existing manuscripts are research background. Their four-term accounting
is conditional on its stated assumptions. The historical submitted-PDF issues
remain documented in the [reproducibility audit](docs/audits/manuscript-reproducibility.md).

The scope reduction and recoverable Git snapshots are recorded in
[repository history](docs/history-merge.md). `AGENTS.md` describes safe development.
