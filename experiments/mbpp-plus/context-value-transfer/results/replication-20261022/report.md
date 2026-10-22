# MBPP+ recovery replication

Status: **incomplete_descriptive_bank**. 376 initial tasks; 134 public failures; 94/96 selected states complete.

Initial census: 376 observed responses and 1 censored admission among 377 eligible tasks. The late censored prefix cannot change the already-observed selected cohort.

The primary is state minus feedback-only policy net utility at the $0.01 task ceiling, original draws 0 and 1.

Estimate **$+0.00011119/failure**, task-bootstrap 95% interval **[$-0.00042595, $+0.00064848]**.

An interval spanning zero does not establish equivalence or an improvement. Complete-case intervals are descriptive if the bank is incomplete.

## Conditional single-draw success

| Model | Fresh | Code | Feedback | Both | Distractor |
|---|---:|---:|---:|---:|---:|
| small | 48.6% | 26.6% | 52.8% | 30.9% | 43.3% |
| large | 61.3% | 50.4% | 62.4% | 58.5% | 61.7% |

## Prespecified context contrasts

All effects are percentage points. Bonferroni intervals use a nominal 95% family level across eight within-model contrasts and four model-by-context interactions.

| Model | Contrast | Effect | 95% | Simultaneous 99.583% |
|---|---|---:|---:|---:|
| small | artifact-fresh | -22.0 | [-29.8, -14.2] | [-33.7, -10.6] |
| small | artifact_feedback-fresh | -17.7 | [-25.5, -10.3] | [-29.4, -6.7] |
| small | artifact_feedback-feedback | -22.0 | [-30.1, -14.5] | [-33.7, -11.0] |
| small | artifact_feedback-distractor | -12.4 | [-20.2, -5.0] | [-24.2, -0.7] |
| large | artifact-fresh | -11.0 | [-17.7, -4.6] | [-21.3, -1.8] |
| large | artifact_feedback-fresh | -2.8 | [-9.6, +3.9] | [-12.8, +6.7] |
| large | artifact_feedback-feedback | -3.9 | [-11.0, +2.8] | [-14.2, +5.3] |
| large | artifact_feedback-distractor | -3.2 | [-9.9, +3.2] | [-13.1, +6.0] |
| small effect minus large effect | artifact-fresh | -11.0 | [-19.9, -2.5] | [-24.5, +1.4] |
| small effect minus large effect | artifact_feedback-fresh | -14.9 | [-24.5, -5.3] | [-29.5, -1.1] |
| small effect minus large effect | artifact_feedback-feedback | -18.1 | [-27.7, -9.2] | [-31.6, -5.3] |
| small effect minus large effect | artifact_feedback-distractor | -9.2 | [-17.7, -0.4] | [-22.0, +3.5] |

## Two-draw policies at $0.01

Conditional on the sampled failed prefix. Direct controls omit producer cost and refer only to this failure population.

| Policy | Success | Mean API dollars | Net utility |
|---|---:|---:|---:|
| global | 64.9% | $0.00068996 | $0.00579940 |
| task | 57.4% | $0.00013641 | $0.00560827 |
| feedback | 52.1% | $0.00012066 | $0.00509211 |
| state | 53.2% | $0.00011585 | $0.00520330 |
| state_model_only | 39.4% | $0.00013176 | $0.00380441 |
| best_static | 63.8% | $0.00055505 | $0.00582793 |
| direct_small | 56.4% | $0.00007482 | $0.00556348 |
| direct_large | 63.8% | $0.00053340 | $0.00584957 |
| escalation_diagnostic | 61.7% | $0.00026911 | $0.00590110 |
| fixed:large.artifact | 54.3% | $0.00065492 | $0.00477061 |
| fixed:large.artifact_feedback | 62.8% | $0.00065166 | $0.00562493 |
| fixed:large.feedback | 64.9% | $0.00068996 | $0.00579940 |
| fixed:large.fresh | 63.8% | $0.00055505 | $0.00582793 |
| fixed:small.artifact | 33.0% | $0.00010353 | $0.00319434 |
| fixed:small.artifact_feedback | 39.4% | $0.00013176 | $0.00380441 |
| fixed:small.feedback | 57.4% | $0.00013641 | $0.00560827 |
| fixed:small.fresh | 56.4% | $0.00009646 | $0.00554183 |

The escalation_diagnostic is an additional fixed 9B-fresh then 27B-fresh replay, added after recovery collection began. It does not replace the frozen primary or transfer a newly generated child's code.

## Prediction and limitations

| View | Brier | Observed benefit MSE |
|---|---:|---:|
| global | 0.279996 | 0.149193 |
| task | 0.417179 | 0.162368 |
| feedback | 0.471458 | 0.157744 |
| state | 0.471100 | 0.159681 |

State-feedback benefit-MSE difference: `{'estimate': 0.0019374069983856034, 'low': -0.0029058348149686086, 'high': 0.00732630086147294, 'tasks': 94, 'alpha': 0.05}`.

Initial public false positives: 40; branch false positives: 360; explicit provider errors: 3.

Collection accounting: `{'admissions': 3257, 'responses': 3254, 'known_cost_usd': 0.83799455, 'unresolved_reservations_usd': 0.0145152, 'prior_upper_usd': 0.5149634, 'campaign_upper_usd': 1.36747315}`.

This is one benchmark/producer/provider pair and one checkpoint. Cheap structural artifact features do not exhaust semantic artifact value. Task lengths shift across benchmarks. Character-matched distractors are not token-matched; see token receipts in analysis.json. Model pretraining contamination cannot be ruled out. No general multi-step controller or CodeRescue reproduction is established.

The former HumanEval+ evaluation is now training data for this replica. Keep its earlier frozen evaluation result separate. Sensitivity rotations, all budgets/actions, noisy-benefit diagnostics and feature shifts are in analysis.json. No secondary test is substituted for the primary.

Missing selected-state worst-case utility bounds: `{'low': -0.00030779166666666677, 'high': 0.0005255416666666666}`.

## Transport censoring

Censored solver admissions (never reissued): `[{'action': 'branch', 'arm': 'artifact', 'call': 1791, 'checkpoint_id': '130', 'donor_checkpoint_id': None, 'draw': 2, 'http_metadata': {}, 'http_status': None, 'model_name': 'large', 'outcome': 'no_preserved_response_identity; reservation retained', 'parent_call': 130, 'retry_after': None, 'task_id': 'Mbpp/426'}, {'action': 'branch', 'arm': 'fresh', 'call': 2817, 'checkpoint_id': '237', 'donor_checkpoint_id': None, 'draw': 0, 'http_metadata': {}, 'http_status': None, 'model_name': 'small', 'outcome': 'no_preserved_response_identity; reservation retained', 'parent_call': 237, 'retry_after': None, 'task_id': 'Mbpp/84'}]`.

Human-authorized continuation after a transport stop and partial descriptive audit; only never-admitted cells. Original estimands/weights fixed, but bank remains incomplete and intervals descriptive.

## Prespecified outcome-blind semantic control

Prompt/code/config were fixed before recovery outcomes, but these forecast responses were collected afterwards. This is secondary and does not replace the physically prospective primary.

Complete matched semantic forecasts: 94/96; malformed forecasts: 0.

| API view | Brier | Observed benefit MSE | Two-draw success | Mean API dollars |
|---|---:|---:|---:|---:|
| task_only | 0.332669 | 0.222145 | 54.3% | $0.00055830 |
| feedback_only | 0.291994 | 0.264068 | 48.9% | $0.00050439 |
| state | 0.329437 | 0.272256 | 52.1% | $0.00047711 |

Full-state minus feedback-only net utility: `{'estimate': 0.0003464329787234042, 'low': -0.00030521819148936164, 'high': 0.0010246263829787226, 'tasks': 94, 'alpha': 0.05}`.

Secondary collection accounting: `{'responses': 288, 'known_cost_usd': 0.0285302, 'unresolved_reservations_usd': 0.0, 'campaign_upper_usd': 1.39600335}`.

Forecaster fees and advance admission ceilings are included. Missing states/forecasts are not free predictions; any complete-case comparison is descriptive if a selected state is absent.
