# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.05`
Cost metric: `wall_seconds`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `9.629732`
- Pilot router holdout objective: `4.963889`
- Oracle router holdout objective: `4.425883`
- Pilot router information gain (nats): `0.442480`
- Pilot router mismatch to oracle (nats): `0.053002`

## Routing Triviality

- Pilot sufficient condition fires: `False`
- Pilot routing trivial empirically: `False`
- Holdout routing trivial empirically: `False`

## Figures

- success_heatmap: `artifacts/oracle_family_decomposition_rel5_topup_partial/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_decomposition_rel5_topup_partial/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_decomposition_rel5_topup_partial/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_decomposition_rel5_topup_partial/pairwise_crossover.png`

## Pairwise Crossover

- Smaller model: `gpt-5.3-codex-spark`
- Larger model: `gpt-5.3-codex`
- Cost ratio: `4.211429`
- Aggregate crossover depth: `4096.000000`

## Pairwise Terms

- Baseline model: `gpt-5.3-codex-spark`
- Comparison model: `gpt-5.3-codex`
- Cost term: `-1.437802`
- Competence term: `5.716287`
