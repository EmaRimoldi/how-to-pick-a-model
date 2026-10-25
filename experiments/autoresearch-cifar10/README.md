# AutoResearch / CIFAR-10

These studies use small CIFAR-10 training programs as a verifiable edit/verify
substrate. Agents propose changes, the evaluator trains the candidate, and
validation loss determines the outcome. The calibration studies establish the
measurement protocol before interpreting agent comparisons.

| Study | What was performed | Evidence and limits |
| --- | --- | --- |
| [Starting-model calibration](starting-model-calibration/) | Predefined edits of batch size, learning rate, capacity, schedule and optimizer to select an improvable baseline | 161 controlled evaluations; this is calibration, not a live-agent comparison. The decision evidence uses 1,170 optimizer updates. |
| [Evaluator and compute calibration](evaluation-protocol-and-compute-calibration/) | Repeatability checks and CPU contention comparisons under fixed-time and fixed-step evaluation | Fixed seed/steps make repeated scores deterministic; equal wall time does not guarantee equal training compute. |
| [Memory ablation](shared-memory-ablation/) | Single/parallel Claude Haiku trials varying shared/private memory, prompt-level search style and hints | 11 valid exploratory trials, one execution per condition. Raw live-agent directories are not included; results support narrow descriptive comparisons. |
| [Three-worker model routing](three-worker-model-routing/) | Three worker aliases on MLP, compact CNN and micro-ResNet workloads, 30 trials per cell, up to 20 edit/verify steps | 270 processed records; full raw traces cover 180. Success is at least 5% relative loss improvement. |

These bundles use different starting points and evaluation protocols. Their
scores and success counts must not be pooled as one controlled benchmark. The
routing workers are the recorded aliases `gpt_5_3_codex`, `gpt_5_4` and
`gpt_5_4_mini`; memory-study search-style directives are not actual API sampling
temperature settings.

The studies motivate the checkpoint-continuation question in the
[decision protocol](../../docs/decision-protocol.md). Existing runs do not
establish outcomes for unobserved restarts or model handoffs. Use the individual
bundle READMEs for methods and limitations, and
[reproducibility](../../docs/reproducibility.md) for safe analysis commands.
