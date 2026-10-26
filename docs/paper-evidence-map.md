# Paper Evidence Map

The [prospective MBPP+ replica](../experiments/mbpp-plus/context-value-transfer/PROTOCOL.md)
adds an external benchmark and the missing feedback-only prediction control.
For that new study, all 51 prior HumanEval+ failures are training data, including
the 25 formerly held-out failures. Keep the original frozen result intact and
separate. Do not count those tasks as a second independent evaluation.

The [completed MBPP+ bank](../experiments/mbpp-plus/context-value-transfer/results/replication-20261022/README.md)
has 94/96 complete selected failures, 2,878 observed recovery draws, two censored
solver cells and 288 API forecasts. Complete-case intervals are descriptive;
all selected states remain in missing-state utility bounds. The primary
state-minus-feedback selector advantage is not established. Context effects
differ across the two model settings, which does not imply that a selector can
predict their task-level value. A [separate empirical draft](paper/recovery-value/README.md)
contains the audited comparisons; existing manuscripts remain separate.

The existing manuscripts and theory are baseline research for the sequential
model-decision question in [decision protocol](decision-protocol.md). They do
not establish that a state-conditioned continue/restart/handoff controller works.

## Claims and boundaries

| Claim family | Theory | Retained evidence | Boundary |
| --- | --- | --- | --- |
| First-passage accounting | `main.tex`, `theory_anchor.tex` | [Archived CIFAR-10 routing](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/provenance/verified-cleanup-2026-10-25/experiments/autoresearch-cifar10/three-worker-model-routing) | Include failures and raw-coverage limits |
| Routing information | `thm:ri-identity` | `experiments/humaneval-plus/strategy-by-difficulty-grid/`, `experiments/humaneval-plus/llm-router-context-search/` | Conditional on the stated model; no universal value-of-information claim |
| Cost/competence/information/mismatch | `thm:four-term` | Archived CIFAR-10 accounting and retained HumanEval+ routing | Diagnostic under assumptions, not an exact law for arbitrary workflows |
| Retry crossover | `thm:retry-crossover` | `experiments/humaneval-plus/retry-allocation-router/` | Replay follows the recorded retry protocol, not arbitrary handoffs |
| Historical memory/context effects | `theory_anchor.tex` | [Archived exploratory memory study](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/provenance/pre-curation-2026-10-24/experiments/autoresearch-cifar10/shared-memory-ablation) | Not an active comparison; limited replication and missing raw run directories |
| Failed-code value and one-checkpoint selection | Frozen empirical protocol | `experiments/humaneval-plus/context-value/` | 25 evaluation failures; producer transfer; no reliable gain over stronger static control |
| Cross-benchmark artifact versus feedback information | Frozen transfer protocol | `experiments/mbpp-plus/context-value-transfer/` | 94/96 complete failures; descriptive censored bank; no established primary selector gain |
| Fixed feedback-only escalation on new tasks | Frozen BigCodeBench protocol | `experiments/bigcodebench/feedback-only-routing/` | Complete 157-task bank; primary −2.55 pp [−7.01, +1.27]; one requested interim look disclosed; unequal admission utilization and public-test false positives |

## Evidence tiers

### Tier 1: Main Evidence

- `experiments/humaneval-plus/strategy-by-difficulty-grid/`
- `experiments/humaneval-plus/llm-router-context-search/`
- `experiments/humaneval-plus/retry-allocation-router/`

### Tier 2: Supporting Or Diagnostic Evidence

- `experiments/humaneval-plus/qwen-model-size-frontier/`
- `experiments/humaneval-plus/context-value/` (discovery and amended transfer; not a current manuscript claim)
- `experiments/mbpp-plus/context-value-transfer/` (censored external replica; separate empirical draft)
- `experiments/bigcodebench/feedback-only-routing/` (complete fixed-policy study; no established primary gain or new selector)

- `experiments/python-repair/checkpoint-environment/` (results in `results/gemma4b-calibration-20261026/`: incomplete 12-bug development pilot; 84 responses, no observed recovery success; no fitted selector or held-out claim)

### Tier 3: Engineering Only — No Model Evidence

- The Python repair bundle’s scripted demo and reference-task qualification remain engineering evidence, distinct from its separately reported paid calibration.

## Recovery evidence and remaining gaps

The completed [feedback-only study](../experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022/report.md)
retains every one of 157 task clusters and 628 policy outcomes. The fixed primary
gain is not established; no selector is built. Its [research-note draft](blog/feedback-only-escalation.md)
reports all four policies, conservative admission, mean/median latency, public
false positives and the one directly requested descriptive interim look, without
replacing the primary with a favorable secondary. Cost point estimates are not
evidence of noninferior quality; stronger public verification has not been tested
as an intervention. Keep this complete bank distinct from within-task sampling,
the censored MBPP+ study and existing manuscripts. These tasks are now observed;
a future intervention/selector requires a new freeze and independent evaluation.

The [archived initial pilot records](../experiments/humaneval-plus/context-value/provenance/continuation-pilot/README.md)
preserve two failed development checkpoints, their receipts and the collector configuration;
this is provenance rather than a separate maintained experiment.
The [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md)
adds prospectively recorded zero-shot forecasts and a code/feedback factorial;
its discovery is diagnostic evidence rather than an additional manuscript result.
The separate [frozen transfer protocol](../experiments/humaneval-plus/context-value/VALIDATION.md)
implements task/state ridge baselines, prospective API forecasts, matched context
controls and budgeted replay. The original same-producer evaluation was stopped
before any observed evaluation response; the declared substitute uses Ministral
failures with the same frozen Gemma-trained policy. Do not describe transfer as
same-producer IID validation or equate a predictor's Brier score with a policy gain.
The [completed report](../experiments/humaneval-plus/context-value/results/validation-20261022/report.md)
finds a positive primary utility difference against the per-draw fixed control,
but the interval against the stronger replay-selected fixed control spans zero.
The [blog draft](blog/when-to-keep-failed-code.md) includes both comparisons and
negative benefit-prediction findings. Its 60 evaluation tasks are now observed;
future tuning needs a fresh holdout. The original 19 reserve tasks remain unused.

The current manuscripts are unchanged. Any new method claim still needs direct
comparisons with the [closest prior work](recovery-related-work.md), a feedback-only
prediction ablation, independent task-family/provider replication and realistic
multi-step tests. Re-FORC, AI Functions, CodeRescue and the other cited systems are
references, not reproduced implementations in this repository.

Run `uv run python scripts/maintenance/workflow.py check` for structure and unit tests. CIFAR-10 reproduction requires
its archived sources; current saved-data replays cover the seven coding-task studies.
