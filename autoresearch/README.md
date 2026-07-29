# AutoResearch CIFAR-10 Infrastructure

This directory contains the runnable AutoResearch infrastructure used by the
model-routing experiment in `experiments/autoresearch-cifar10/three-worker-model-routing/`.

## Canonical Reproduction Surface

- `benchmark/cifar10/`: editable CIFAR-10 training benchmark, workload templates,
  verifier wrapper, metadata, and solution validation.
- `configs/`: active AutoResearch run configs. The current model-routing config
  uses `gpt_5_3_codex`, `gpt_5_4`, and `gpt_5_4_mini`.
- `prompts/`: canonical model-generation and router prompts.
- `analysis/`: modules used to launch pilots, compute threshold/accounting
  reports, and analyze router decisions.
- `scripts/`: plotting, artifact, Slurm, and campaign helper scripts.

The canonical workload set is:

- `cnn_compact`
- `mlp_flat`
- `resnet_micro`

Each run uses a 20-step proposal horizon and a 5% relative validation-loss
improvement threshold unless the config says otherwise.

## Lightweight Local Substrate

The root-level files `prepare.py`, `train.py`, and `program.md` support the
lightweight CLI demo/runtime path. They are useful for local workflow smoke
tests, but they are not the full model-routing reproduction harness.

## Safe Local Checks

These commands verify the infrastructure without launching live agents or
rerunning expensive training:

```bash
PYTHONPATH=src:. uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
PYTHONPATH=src:. uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/agent_workflow_autoresearch_reproduced
```

Full reruns require the `autoresearch` optional dependency profile for
Torch/Torchvision, Claude Code or Codex CLI model access, and enough CPU/GPU
capacity for CIFAR-10 verification.
