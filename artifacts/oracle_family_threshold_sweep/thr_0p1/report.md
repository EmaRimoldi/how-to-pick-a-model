# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.1`
Cost metric: `wall_seconds`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `10.653411`
- Pilot router holdout objective: `8.891713`
- Oracle router holdout objective: `4.516289`
- Pilot router information gain (nats): `0.063492`
- Pilot router mismatch to oracle (nats): `0.621210`

## Routing Triviality

- Pilot sufficient condition fires: `True`
- Pilot routing trivial empirically: `True`
- Holdout routing trivial empirically: `False`

## Figures

- success_heatmap: `artifacts/oracle_family_threshold_sweep/thr_0p1/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_threshold_sweep/thr_0p1/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_threshold_sweep/thr_0p1/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_threshold_sweep/thr_0p1/pairwise_crossover.png`

## Pairwise Crossover

- Smaller model: `gpt-5.3-codex-spark`
- Larger model: `gpt-5.3-codex`
- Cost ratio: `4.329814`
- Aggregate crossover depth: `4096.000000`
