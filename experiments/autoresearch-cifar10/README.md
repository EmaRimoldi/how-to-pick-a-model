# AutoResearch / CIFAR-10

These bundles contain only AutoResearch CIFAR-10 edit--verify evidence:

- [`starting-model-calibration/`](starting-model-calibration/): selects the
  starting `train.py` and measures available headroom.
- [`evaluation-protocol-and-compute-calibration/`](evaluation-protocol-and-compute-calibration/):
  separates evaluator determinism, fixed-step comparisons, and compute contention.
- [`shared-memory-ablation/`](shared-memory-ablation/): compares independent
  exploration with a shared-memory workflow.
- [`swarm-vs-independent-agents/`](swarm-vs-independent-agents/): preserves
  historical swarm and parallel-agent baselines.
- [`three-worker-model-routing/`](three-worker-model-routing/): contains the
  worker frontier, routing/accounting results, raw traces, and paper figures.

Use [`reproducibility.md`](reproducibility.md) for commands and
[`catalog.md`](catalog.md) for evidence status.
