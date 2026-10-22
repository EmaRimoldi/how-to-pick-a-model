# Held-out producer-transfer recovery evaluation

83 development tasks (26 failed); 60 untouched evaluation tasks (25 failed).

Development producer: `google/gemma-3-4b-it`; evaluation producer: `mistralai/ministral-3b-2512`. The original same-producer evaluation is not claimed complete.

Development-selected fixed action: `large.feedback`.

Primary state-ridge minus best-fixed net utility at $0.01/task: +0.00040765 USD; task-bootstrap 95% interval [3.4823770833333404e-05, 0.0009522526875000001].

| Policy at $0.01/task | Full verified success | Mean API USD | Mean net utility USD |
| --- | --- | --- | --- |
| direct_small | 83.3% | 0.00007357 | 0.00825977 |
| direct_large | 88.3% | 0.00072849 | 0.00810484 |
| best_fixed | 88.3% | 0.00044596 | 0.00838737 |
| development_replay_best | 91.7% | 0.00040016 | 0.00876651 |
| global | 88.3% | 0.00044596 | 0.00838737 |
| task | 88.3% | 0.00044504 | 0.00838830 |
| state | 91.7% | 0.00037164 | 0.00879502 |
| api_task_only | 91.7% | 0.00048661 | 0.00868006 |
| api_state | 93.3% | 0.00048960 | 0.00884373 |
| state_model_only | 93.3% | 0.00043642 | 0.00889691 |
| state_context_small | 88.3% | 0.00008764 | 0.00874570 |
| state_context_large | 88.3% | 0.00042959 | 0.00840374 |

| Conditional recovery | Success | Mean next-attempt API USD | Task-bootstrap 95% interval |
| --- | --- | --- | --- |
| small.fresh | 66.0% | 7.0321e-05 | [0.48, 0.82] |
| small.artifact | 50.0% | 8.367e-05 | [0.32, 0.68] |
| small.feedback | 64.0% | 9.3793e-05 | [0.48, 0.8] |
| small.artifact_feedback | 62.0% | 9.627e-05 | [0.44, 0.78] |
| small.distractor | 64.0% | 9.9382e-05 | [0.48, 0.8] |
| large.fresh | 84.0% | 0.0008503299999999999 | [0.7, 0.96] |
| large.artifact | 86.0% | 0.00075641 | [0.72, 0.98] |
| large.feedback | 80.0% | 0.000914 | [0.64, 0.94] |
| large.artifact_feedback | 86.0% | 0.000877605 | [0.72, 0.98] |
| large.distractor | 86.0% | 0.00084013 | [0.74, 0.96] |

| Paired context contrast | Success difference | Task-bootstrap 95% interval |
| --- | --- | --- |
| small.both_minus_fresh | -4.0% | [-0.22, 0.12] |
| small.code_minus_fresh | -16.0% | [-0.3, -0.04] |
| small.feedback_minus_fresh | -2.0% | [-0.12, 0.08] |
| small.both_minus_distractor | -2.0% | [-0.18, 0.14] |
| large.both_minus_fresh | +2.0% | [-0.08, 0.12050000000000181] |
| large.code_minus_fresh | +2.0% | [-0.08, 0.14] |
| large.feedback_minus_fresh | -4.0% | [-0.16, 0.06] |
| large.both_minus_distractor | +0.0% | [-0.06, 0.06] |

| Predictor | Brier | Observed benefit MSE |
| --- | --- | --- |
| global | 0.191031 | 0.115593 |
| task | 0.190596 | 0.120648 |
| state | 0.190532 | 0.136158 |
| api_state | 0.216346 | 0.199313 |
| api_task_only | 0.208199 | 0.181766 |

| Secondary paired predictor difference (negative favors first) | Brier difference, 95% interval | Benefit MSE difference, 95% interval |
| --- | --- | --- |
| state_minus_task | -0.000064, [-0.02276173346206923, 0.023405142469905146] | +0.015510, [-0.005183416945348777, 0.0376440064079501] |
| state_minus_global | -0.000498, [-0.02736096918728484, 0.024727848525253445] | +0.020565, [-0.006055158408478701, 0.0475880634407609] |
| api_state_minus_api_task_only | +0.008146, [-0.022924787500000005, 0.038132937500000005] | +0.017547, [-0.025313225000000026, 0.06648565000000002] |

Collection: 1359 request admissions, $0.48364660; previous committed spend $0.02302240; known combined $0.50666900. Unobserved transport admissions retain $0.00829440; conservative combined upper bound $0.51496340 within the $2 ceiling.

Explicit empty provider errors normalized to policy-backed zero charge: 7. They remain failed draws. Raw usage and billing provenance are preserved; unknown non-error billing still stops collection.

Measured costs include recorded failed responses. Recovery rollouts pay the producer prefix and API predictors pay their forecasting fee. Admission uses the advance reservation, not future receipts. Policies stop on public-base success; Plus outcomes never select an action. Direct models do not pay a producer-prefix fee.

Two-draw banks constrain every policy: these are not unlimited retry or multi-step controller claims. Conditional rates average draws per independent failed task. Bootstrap resamples held-out tasks, 4000 times with seed 20261024; secondary comparisons have no multiplicity-adjusted significance claim. Observed benefit MSE includes two-draw measurement noise and is not error against true individual effects.

Distractor fields are character matched; provider token counts are recorded in analysis.json. The producer and next solvers differ in family/training/precision. Task-level holdout does not remove possible pretraining contamination of HumanEval+. This remains one benchmark family and one live provider snapshot.

Secondary replay-selected fixed actions by budget: {'0.003': 'small.feedback', '0.01': 'large.fresh', '0.02': 'large.fresh'}.
State-ridge minus this stronger fixed comparator at $0.01/task: {'mean': 2.8514166666666723e-05, 'task_clusters': 60, 'bootstrap_95': [-0.00046099427083333335, 0.0005402700833333336]}.

Producer changed from `google/gemma-3-4b-it` via `deepinfra/bf16` to `mistralai/ministral-3b-2512` via `mistral` before any evaluation response, after rate-limit stops. This is a producer-transfer evaluation, not same-producer IID validation. All unknown admissions remain reserved as collection overhead; no zero-cost receipts or task outcomes are invented. Policy replay bills concern the complete observed bank and do not fully identify deployment outage/retry cost.
