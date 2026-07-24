# AutoResearch experiments

This directory contains only AutoResearch/CIFAR-10 evidence.

- [`01_baseline/`](01_baseline/): starting-task calibration.
- [`02_evaluation_protocol_calibration/`](02_evaluation_protocol_calibration/):
  fixed-step and evaluator calibration.
- [`03_agent_memory_ablation/`](03_agent_memory_ablation/): shared-memory
  workflow comparison.
- [`04_swarm_baselines/`](04_swarm_baselines/): swarm and independent-parallel
  baselines.
- [`05_autoresearch_model_routing/`](05_autoresearch_model_routing/): worker
  frontier, routing, accounting, raw traces, and paper figures.

Use [`reproducibility.md`](reproducibility.md) for per-experiment commands and
[`../../docs/reproducibility-autoresearch.md`](../../docs/reproducibility-autoresearch.md)
for the runtime setup.
