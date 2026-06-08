# AutoResearch

This directory contains the complete AutoResearch CIFAR-10 experiment surface.

## Layout

- `benchmark/cifar10/`: editable CIFAR-10 training benchmark, verifier wrapper, workload templates, and metadata.
- `configs/`: active run configs.
- `prompts/`: model-generation and router prompts.
- `analysis/`: launchers and accounting modules used as `python -m autoresearch.analysis...`.
- `scripts/`: Slurm helpers, campaign utilities, figure builders, and artifact builder.
- `campaigns/h20_delta005_20260505/`: frozen paper-facing campaign snapshot and processed accounting.
- `paper_figures/current/`: generated figures used by the paper.
- `tests/`: AutoResearch-specific smoke tests.
- `legacy/`: pre-canonical diagnostics and historical analyses kept for reference.

## Canonical Protocol

- Workloads: `cnn_compact`, `mlp_flat`, `resnet_micro`.
- Horizon: `H=20`.
- Success threshold: relative validation-loss improvement `delta=0.05`.
- Verifier budget: `AUTOSEARCH_MAX_STEPS=256`.
- Candidate generation: `interactive_session` for real-model trajectories.
- Worker menu: `gpt_5_3_codex`, `gpt_5_4`, `gpt_5_4_mini`.
- Prompt: `autoresearch_program.txt`.

`resnet_tiny`, synthetic bottleneck initial states, and `legacy/` scripts are
retained only as historical/debugging material; they are not part of the
canonical three-mode paper protocol.

## Common Commands

```bash
PYTHONPATH=src:. ./.venv/bin/python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml \
  --models gpt_5_3_codex,gpt_5_4,gpt_5_4_mini \
  --workloads cnn_compact,mlp_flat,resnet_micro \
  --seeds 7001:2 \
  --split pilot
```

```bash
PYTHONPATH=src:. ./.venv/bin/python -m autoresearch.analysis.autoresearch_cifar10_threshold_sweep \
  autoresearch/runs/workload_pilot autoresearch/runs/workload_holdout \
  --output autoresearch/artifacts/workload_threshold_report.json
```
