# How to Pick a Model

Theory, executable benchmarks, and empirical evidence for deployment-aware
model and agent selection.

This repository unifies the former `theory-of-agents`, `agentops-lab-public`,
and Overleaf manuscript histories. It keeps the paper, AutoResearch evidence,
and the HumanEval+/MBPP+/BBH strategy-routing work in one place while preserving
clear experimental boundaries.

## Repository map

- `paper/`: submitted manuscript, LaTeX sources, historical drafts, references,
  and paper figures.
- `autoresearch/`: runnable CIFAR-10 edit--verify benchmark and analysis code.
- `experiments/autoresearch/`: AutoResearch-only experiments and evidence.
- `experiments/other/`: strategy-routing, SWE-bench, and other non-AutoResearch
  experiment artifacts.
- `experiments/other/distribution-aware-orchestration/`: the non-AutoResearch
  archive, Step 1 induction work, and later SWE-bench studies imported from the
  former cluster checkout `NeurIPS_2026`.
- `src/agent_workflow/` and `src/vao/`: orchestration runtime imported from
  `agentops-lab-public`.
- `src/*.py`, `config/`, and `data/`: HumanEval+, MBPP+, BBH, and retry-routing
  pipeline inherited from `theory-of-agents`.
- `configs/`: orchestration and AutoResearch runtime configuration.
- `tests/`: runtime and AutoResearch reproduction tests.

The experiment index is in [`experiments/README.md`](experiments/README.md).

## Quick setup

The unified Python package is named `how-to-pick-a-model`. The historical
`agent-workflow` CLI name remains available for compatibility.

```bash
uv sync --dev --frozen
uv run agent-workflow --help
uv run pytest -q
```

Install optional experiment dependencies only when needed:

```bash
uv sync --dev --extra autoresearch --frozen
uv sync --dev --extra other-experiments --frozen
uv sync --dev --extra all-experiments --frozen
```

## Safe reproduction checks

Regenerate the reader-facing AutoResearch figures from processed evidence:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch/05_autoresearch_model_routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Inspect the non-AutoResearch worker traces without live model calls:

```bash
uv run python -m src.load_traces --config config/router_experiment.yaml
uv run python -m src.load_traces --config config/router_experiment_mbpp_2models.yaml
uv run python -m src.load_traces --config config/router_experiment_bbh.yaml
```

See [`docs/reproducibility.md`](docs/reproducibility.md) for the complete
environment and evidence matrix.

The original repository roots and path mapping are documented in
[`docs/history-merge.md`](docs/history-merge.md).

## Manuscript status

The original submitted PDF is
[`paper/submitted-manuscript.pdf`](paper/submitted-manuscript.pdf). The
reproducibility audit found that its promoted deployment-loss table used a
legacy full-horizon composite loss rather than the first-passage loss stated in
the text. The corrected accounting and later three-worker analysis are the
canonical computational results in this repository. Details are recorded in
[`docs/audits/manuscript-reproducibility.md`](docs/audits/manuscript-reproducibility.md).

## Historical names

The package/CLI compatibility surface still uses `agent_workflow` and
`agent-workflow`; experiment paths and documentation use the unified
`how-to-pick-a-model` project name.
