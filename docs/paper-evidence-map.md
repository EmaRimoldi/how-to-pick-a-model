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
predict their task-level value. A [separate empirical draft](../paper/recovery-value/README.md)
contains the audited comparisons; existing manuscripts remain separate.

The existing manuscripts and theory are baseline research for the sequential
model-decision question in [decision protocol](decision-protocol.md). They do
not establish that a state-conditioned continue/restart/handoff controller works.

## Claims and boundaries

| Claim family | Theory | Retained evidence | Boundary |
| --- | --- | --- | --- |
| First-passage accounting | `main.tex`, `theory_anchor.tex` | `experiments/autoresearch-cifar10/three-worker-model-routing/` | Include failures and raw-coverage limits |
| Routing information | `thm:ri-identity` | `experiments/humaneval-plus/strategy-by-difficulty-grid/`, `experiments/humaneval-plus/llm-router-context-search/` | Conditional on the stated model; no universal value-of-information claim |
| Cost/competence/information/mismatch | `thm:four-term` | AutoResearch accounting and HumanEval+ routing | Diagnostic under assumptions, not an exact law for arbitrary workflows |
| Retry crossover | `thm:retry-crossover` | `experiments/humaneval-plus/retry-allocation-router/` | Replay follows the recorded retry protocol, not arbitrary handoffs |
| Memory/context effects | `theory_anchor.tex` | `experiments/autoresearch-cifar10/shared-memory-ablation/` | Substrate-specific baseline, not proof of a cross-model transfer benefit |
| Failed-code value and one-checkpoint selection | Frozen empirical protocol | `experiments/humaneval-plus/context-value/` | 25 evaluation failures; producer transfer; no reliable gain over stronger static control |
| Cross-benchmark artifact versus feedback information | Frozen transfer protocol | `experiments/mbpp-plus/context-value-transfer/` | 94/96 complete failures; descriptive censored bank; no established primary selector gain |

## Evidence tiers

### Tier 1: Main Evidence

- `experiments/humaneval-plus/strategy-by-difficulty-grid/`
- `experiments/humaneval-plus/llm-router-context-search/`
- `experiments/humaneval-plus/retry-allocation-router/`
- `experiments/autoresearch-cifar10/three-worker-model-routing/`
- `experiments/autoresearch-cifar10/shared-memory-ablation/`
- `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/`

### Tier 2: Supporting Or Diagnostic Evidence

- `experiments/autoresearch-cifar10/starting-model-calibration/`
- `experiments/humaneval-plus/qwen-model-size-frontier/`
- `experiments/humaneval-plus/context-value/` (discovery and amended transfer; not a current manuscript claim)
- `experiments/mbpp-plus/context-value-transfer/` (censored external replica; separate empirical draft)

## Recovery evidence and remaining gaps

The next [feedback-only fixed-policy protocol](../experiments/bigcodebench/feedback-only-routing/PROTOCOL.md)
uses new BigCodeBench tasks and actual sequential feedback, without code transfer
or a new predictor. It is prospective preparation, not an additional paper result.
Keep its 157 task clusters distinct from within-task sampling and from
the already observed HumanEval+/MBPP+ banks. A selector remains gated on a useful
intervention and a subsequent independently held-out evaluation.

The [OpenRouter development pilot](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md)
provides a collector and matched continuations on two failed development states.
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

Run `make check` for structure and unit tests, and
`make paper-figures-autoresearch` to regenerate three baseline figures.
