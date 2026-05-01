# Task-Mode Bootstrap

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Bootstrap samples: `400`

## Key Numeric Terms

- `pairwise.cost_term`: point=`-1.437802`, 95% bootstrap CI=`[-1.525355, -1.357236]`
- `pairwise.competence_term`: point=`5.716287`, 95% bootstrap CI=`[5.316394, 5.845024]`
- `decomposition.pilot_information_gain_nats`: point=`0.442480`, 95% bootstrap CI=`[0.030116, 0.632102]`
- `decomposition.holdout_information_gain_nats`: point=`0.650213`, 95% bootstrap CI=`[0.618661, 0.676522]`
- `decomposition.pilot_router_mismatch_nats`: point=`0.053002`, 95% bootstrap CI=`[0.000283, 0.625758]`
- `decomposition.single_model_mismatch_nats`: point=`5.893420`, 95% bootstrap CI=`[5.848907, 7.934927]`
- `decomposition.pilot_router_holdout_objective`: point=`4.963889`, 95% bootstrap CI=`[4.409828, 8.462717]`
- `decomposition.oracle_router_holdout_objective`: point=`4.425883`, 95% bootstrap CI=`[4.383408, 4.508335]`
- `decomposition.single_best_model_holdout_objective`: point=`9.629732`, 95% bootstrap CI=`[5.182230, 9.702911]`

## Key Boolean Terms

- `triviality.pilot.sufficient_condition_fires`: point=`False`, bootstrap true-rate=`0.113`
- `triviality.pilot.routing_is_trivial_empirically`: point=`False`, bootstrap true-rate=`0.113`
- `triviality.holdout.sufficient_condition_fires`: point=`False`, bootstrap true-rate=`0.000`
- `triviality.holdout.routing_is_trivial_empirically`: point=`False`, bootstrap true-rate=`0.000`
