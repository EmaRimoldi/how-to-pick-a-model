# Task-Mode Bootstrap

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Bootstrap samples: `400`
- Task-mode priors: `uniform`

## Key Numeric Terms

- `pairwise.cost_term`: point=`-1.424074`, 95% bootstrap CI=`[-1.497206, -1.317834]`
- `pairwise.competence_term`: point=`6.816595`, 95% bootstrap CI=`[6.561182, 6.907755]`
- `decomposition.pilot_information_gain_nats`: point=`0.510121`, 95% bootstrap CI=`[0.087723, 0.647875]`
- `decomposition.holdout_information_gain_nats`: point=`0.660070`, 95% bootstrap CI=`[0.634815, 0.685530]`
- `decomposition.pilot_router_mismatch_nats`: point=`0.033307`, 95% bootstrap CI=`[0.000297, 0.512899]`
- `decomposition.single_model_mismatch_nats`: point=`6.959221`, 95% bootstrap CI=`[6.687769, 7.015542]`
- `decomposition.pilot_router_holdout_objective`: point=`4.894107`, 95% bootstrap CI=`[4.523456, 8.472099]`
- `decomposition.oracle_router_holdout_objective`: point=`4.541397`, 95% bootstrap CI=`[4.504644, 4.624968]`
- `decomposition.single_best_model_holdout_objective`: point=`10.695749`, 95% bootstrap CI=`[5.189377, 10.778405]`

## Key Boolean Terms

- `triviality.pilot.sufficient_condition_fires`: point=`False`, bootstrap true-rate=`0.085`
- `triviality.pilot.routing_is_trivial_empirically`: point=`False`, bootstrap true-rate=`0.085`
- `triviality.holdout.sufficient_condition_fires`: point=`False`, bootstrap true-rate=`0.000`
- `triviality.holdout.routing_is_trivial_empirically`: point=`False`, bootstrap true-rate=`0.000`
