# Theory of Agents

Empirical proper-time and retry-allocation experiments for evaluating when
multiple local language models should be routed, retried, or ignored.

This repository contains three related experiment tracks:

- **HumanEval+ proper-time frontier:** Qwen2.5-Coder 1.5B, 7B, and 32B on
  HumanEval+, with repeated sampling until verified pass or censoring.
- **Retry-allocation router:** a Codex/LLM router allocates a fixed retry budget
  across workers using saved traces, then execution is simulated from logs.
- **Dataset extensions:** MBPP+ and BBH variants reuse the same worker-log,
  allocation, router, estimator, and plotting pipeline.

## Quick Setup

Use the project-local virtual environment. The local `.venv/` is intentionally
not committed; recreate it from the pinned requirements file.

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m compileall -q src
```

External tools for live runs:

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:32b
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:7b
ollama pull qwen2.5:32b
```

Router/category experiments that use Codex CLI also require:

```bash
export ROUTER_MODEL=<codex-model-id>
```

## What Is Reproducible From Tracked Files

Read [`docs/reproducibility.md`](docs/reproducibility.md) for the exact
experiment-by-experiment matrix.

Safe read-only checks:

```bash
.venv/bin/python -m src.load_traces --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
.venv/bin/python -m src.load_traces --config experiments/mbpp-plus/two-model-retry-router/configs/router.yaml
.venv/bin/python -m src.load_traces --config experiments/bbh/family-and-subtask-router/configs/router_experiment_bbh.yaml
```

Figure and estimator scripts are separated from live model calls. Some smoke
scripts intentionally delete/regenerate local smoke outputs; run them only from a
clean worktree or after reading the reproducibility guide.

## Main Commands

HumanEval+ worker frontier:

```bash
scripts/smoke_test.sh
scripts/full_run.sh
```

HumanEval+ retry-allocation router:

```bash
scripts/smoke_router.sh
scripts/full_router_run.sh
```

MBPP+ worker/router variants:

```bash
scripts/smoke_mbpp_worker.sh
scripts/full_run_mbpp_2models.sh
scripts/full_run_mbpp_32b.sh
scripts/full_category_run.sh
```

BBH worker/router variants:

```bash
scripts/smoke_bbh.sh
scripts/full_run_bbh.sh
scripts/full_router_run_bbh.sh
```

## Repository Map

- `src/`: reusable Python modules for datasets, workers, evaluation, routing,
  estimation, and plotting.
- `config/`: YAML configurations for HumanEval+, MBPP+, BBH, and router runs.
- `scripts/`: smoke and full-run launch scripts.
- `data/raw/`: tracked full worker logs used as empirical evidence.
- `data/derived/`: tracked derived summaries, folds, modes, and router outputs.
- `docs/specs/`: original implementation specifications and protocol notes.
- `NOTES.md`: operational notes from the historical runs.

Ignored local artifacts include `.venv/`, `figures/`, `report/`, LaTeX build
outputs, smoke outputs, and local archive material.
