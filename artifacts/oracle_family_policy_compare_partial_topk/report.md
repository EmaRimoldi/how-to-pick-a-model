# Policy Comparison

- Setting: `anytime::tau=0.050`

## Recommended Horizons

- `fixed_indexing`: recommended_horizon=`3`, best_oracle_objective=`3.3631107917833645`
- `fixed_topk`: recommended_horizon=`1`, best_oracle_objective=`17.241276152934482`
- `top1`: recommended_horizon=`2`, best_oracle_objective=`3.459613361016545`

## Trajectory Means

- `holdout` / `fixed_indexing`: best_rel=`0.6998`, terminal_rel=`0.6816`
- `holdout` / `fixed_topk`: best_rel=`0.0201`, terminal_rel=`0.0162`
- `holdout` / `top1`: best_rel=`0.4443`, terminal_rel=`0.4405`
- `pilot` / `fixed_indexing`: best_rel=`0.7083`, terminal_rel=`0.7059`
- `pilot` / `fixed_topk`: best_rel=`0.0147`, terminal_rel=`0.0147`
- `pilot` / `top1`: best_rel=`0.7146`, terminal_rel=`0.6484`
