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
experiments/autoresearch/01_baseline/
experiments/autoresearch/02_evaluation_protocol_calibration/
experiments/autoresearch/03_agent_memory_ablation/
experiments/autoresearch/04_swarm_baselines/
experiments/autoresearch/05_autoresearch_model_routing/
```

Safe checks:

```bash
uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch/05_autoresearch_model_routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Full instructions: [`reproducibility-autoresearch.md`](reproducibility-autoresearch.md).

## Other experiments

The HumanEval+, MBPP+, and BBH pipeline uses `config/`, root-level `src/*.py`,
and tracked `data/`.

Safe trace checks:

```bash
uv run python -m src.load_traces --config config/router_experiment.yaml
uv run python -m src.load_traces --config config/router_experiment_mbpp_2models.yaml
uv run python -m src.load_traces --config config/router_experiment_bbh.yaml
```

Completed strategy-routing evidence and SWE-bench scaffolding are under
`experiments/other/`.

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
