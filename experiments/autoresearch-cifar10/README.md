# AutoResearch / CIFAR-10

Two maintained bundles use CIFAR-10 training programs as a verifiable edit/verify
substrate. Agents propose changes, the evaluator trains the candidate, and
validation loss determines the outcome.

| Bundle | Scope | Evidence and limits |
| --- | --- | --- |
| [Calibration](calibration/) | Starting-model selection, evaluator repeatability and CPU compute allocation | 161 controlled evaluations, five determinism checks, fixed-time/fixed-step controls; distinct protocols are not pooled. |
| [Three-worker model routing](three-worker-model-routing/) | Three worker aliases across MLP, compact CNN and micro-ResNet workloads, up to 20 edit/verify steps | Primary pooled accounting: 300 records with 35/35/30 trials per workload. Balanced sensitivity: 270 records; raw traces cover 180 of those. Success means at least 5% relative loss improvement. |

The routing workers are the recorded aliases `gpt_5_3_codex`, `gpt_5_4` and
`gpt_5_4_mini`. Scores from different starting points and protocols must not be
pooled as one controlled benchmark.

The exploratory shared-memory ablation and superseded 2×2 pilots are archived
under the [provenance tag](../../docs/history-merge.md); they are not maintained
comparison experiments. The [cleanup record](../../docs/audits/experiment-cleanup.md)
documents their disposition.

These studies motivate the [decision protocol](../../docs/decision-protocol.md).
Existing runs do not establish outcomes for unobserved restarts or model handoffs.
Use [reproducibility](../../docs/reproducibility.md) for safe analysis commands.
