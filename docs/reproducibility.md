# Reproducibility

This is the top-level reproduction map for the unified repository.

## Environment

```bash
uv sync --dev --frozen
uv run pytest -q
```

Optional dependency profiles:

- `autoresearch`: Torch/Torchvision for CIFAR-10 verification.
- `other-experiments`: EvalPlus, Transformers, and related dependencies for
  HumanEval+/MBPP+/BBH.
- `swebench`: SWE-bench and Docker.
- `all-experiments`: all experiment profiles.

Copy `.env.example` to `.env` only when live provider-backed runs are required.
Never commit `.env`.

## AutoResearch

Canonical evidence:

```text
experiments/autoresearch-cifar10/starting-model-calibration/
experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/
experiments/autoresearch-cifar10/shared-memory-ablation/
experiments/autoresearch-cifar10/swarm-vs-independent-agents/
experiments/autoresearch-cifar10/three-worker-model-routing/
```

Safe checks:

```bash
uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Full instructions: [`reproducibility-autoresearch.md`](reproducibility-autoresearch.md).

## Other experiments

The HumanEval+, MBPP+, and BBH pipeline uses root-level `src/*.py`; each
experiment's configs, data, results, and launchers are co-located in its bundle.

Safe trace checks:

```bash
uv run python -m src.load_traces --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/mbpp-plus/two-model-retry-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/bbh/family-and-subtask-router/configs/router_experiment_bbh.yaml
```

Completed strategy-routing evidence is under `experiments/humaneval-plus/`.
SWE-bench scaffolds, runtime code, and dated evidence are under
`experiments/swebench-verified/`.

Full instructions:
[`reproducibility-other-experiments.md`](reproducibility-other-experiments.md).

## Paper

The submitted artifact and source are under `paper/`. Compile the active source
from its own directory so relative figure paths remain valid:

```bash
cd paper/neurips-submission
latexmk -pdf main.tex
```

The known manuscript/result mismatch is documented in
[`audits/manuscript-reproducibility.md`](audits/manuscript-reproducibility.md).
