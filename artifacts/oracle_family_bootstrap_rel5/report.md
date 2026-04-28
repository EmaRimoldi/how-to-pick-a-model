# Task-Mode Bootstrap

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Bootstrap samples: `400`

## Key Numeric Terms

- `pairwise.cost_term`: point=`-1.465525`, 95% bootstrap CI=`[-1.502369, -1.211471]`
- `pairwise.competence_term`: point=`6.907755`, 95% bootstrap CI=`[6.907755, 6.907755]`
- `decomposition.pilot_information_gain_nats`: point=`0.090243`, 95% bootstrap CI=`[0.000588, 0.666912]`
- `decomposition.holdout_information_gain_nats`: point=`0.648885`, 95% bootstrap CI=`[0.636572, 0.652318]`
- `decomposition.pilot_router_mismatch_nats`: point=`0.617580`, 95% bootstrap CI=`[0.000024, 1.985078]`
- `decomposition.single_model_mismatch_nats`: point=`6.984661`, 95% bootstrap CI=`[6.701496, 7.016057]`
- `decomposition.pilot_router_holdout_objective`: point=`8.872806`, 95% bootstrap CI=`[4.504916, 10.554073]`
- `decomposition.oracle_router_holdout_objective`: point=`4.516289`, 95% bootstrap CI=`[4.503783, 4.567561]`
- `decomposition.single_best_model_holdout_objective`: point=`10.653411`, 95% bootstrap CI=`[5.195659, 10.885874]`

## Key Boolean Terms

- `triviality.pilot.sufficient_condition_fires`: point=`True`, bootstrap true-rate=`0.713`
- `triviality.pilot.routing_is_trivial_empirically`: point=`True`, bootstrap true-rate=`0.713`
- `triviality.holdout.sufficient_condition_fires`: point=`False`, bootstrap true-rate=`0.000`
- `triviality.holdout.routing_is_trivial_empirically`: point=`False`, bootstrap true-rate=`0.000`
