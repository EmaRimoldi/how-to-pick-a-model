# OpenRouter continuation pilot

Exploratory one-checkpoint calibration; no learned-controller or generalization claim

Status: `complete`. Complete matched tasks: 24.
Collection cost: $0.024332; unresolved reservations: $0.000000; budget ceiling: $1.98.

| Strategy | Tasks | Full HumanEval+ success | Mean policy cost (USD) |
| --- | --- | --- | --- |
| cheap_stop | 24 | 87.5% | 0.000030 |
| strong_direct | 24 | 91.7% | 0.000389 |
| continue | 24 | 91.7% | 0.000035 |
| restart | 24 | 89.6% | 0.000033 |
| switch_fresh | 24 | 91.7% | 0.000082 |
| switch_context | 24 | 91.7% | 0.000074 |

Policy cost includes the initial small-model attempt plus the chosen action. Collection cost includes every sampled counterfactual branch. Branch repeats from one checkpoint are not independent tasks. Visible-example success stops a policy; the final base/plus scores never trigger retries or appear in model feedback.

This development pilot is excluded from any future held-out evaluation. Passing public examples is not proof of full-suite correctness. This is not a trained controller, a pure parameter-scaling study, or a state-of-the-art result.
