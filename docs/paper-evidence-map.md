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

## Missing evidence for the next question

Matched action continuations, calibrated state-dependent forecasts, and held-out
policy comparisons including switching/context costs remain to be produced.
Keep them labeled as planned. Re-FORC and AI Functions are related-work/baseline
references, not implemented integrations or new results in this repository.

Run `make check` for structure and unit tests, and
`make paper-figures-autoresearch` to regenerate three baseline figures.
