# AutoResearch / CIFAR-10

Retained baseline evidence for verifiable edit/verify decisions:

- [Starting-model calibration](starting-model-calibration/): initial state and headroom.
- [Evaluation controls](evaluation-protocol-and-compute-calibration/): determinism, fixed steps, and contention.
- [Shared memory](shared-memory-ablation/): a substrate-specific context/memory baseline.
- [Three-worker routing](three-worker-model-routing/): model frontier, first-hit accounting, and available raw traces.

These studies motivate the next checkpoint-continuation experiment in
[decision protocol](../../docs/decision-protocol.md). Existing runs do not
establish outcomes for unobserved restarts or model handoffs.

See [reproducibility](../../docs/reproducibility.md) for safe commands.
