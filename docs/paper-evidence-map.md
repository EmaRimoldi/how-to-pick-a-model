# Paper Evidence Map

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

## Recovery evidence and remaining gaps

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
