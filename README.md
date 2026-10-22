# How to Pick a Model

**Cost-aware decisions for verifiable agent tasks.**

The research question is: given the work completed so far, when should an agent
continue, restart, switch models, or stop spending compute?

This repository retains the AutoResearch/CIFAR-10 and HumanEval+ evidence needed
to study that question: verified trajectories, retry-allocation baselines,
context/routing experiments, cost accounting, and reproducible figures.

**Current status:** the retained experiments measure model choice, retries, and
information use. A budgeted [OpenRouter pilot](experiments/humaneval-plus/openrouter-continuation-pilot/README.md)
now includes a runner and a 24-task development dataset with matched actions
on two visibly failed checkpoints. A learned policy still
needs training and held-out evaluation. The baseline traces
are not evidence that an unobserved model handoff would have succeeded.

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
| `experiments/` | Eight baseline bundles and a continuation pilot across two benchmark families |
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
