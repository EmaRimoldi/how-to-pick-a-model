# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.05`
Cost metric: `wall_seconds`
Task-mode priors: `uniform`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `10.695749`
- Pilot router holdout objective: `4.894107`
- Oracle router holdout objective: `4.541397`
- Pilot router information gain (nats): `0.510121`
- Pilot router mismatch to oracle (nats): `0.033307`

## Routing Triviality

- Pilot sufficient condition fires: `False`
- Pilot routing trivial empirically: `False`
- Holdout routing trivial empirically: `False`

## Figures

- success_heatmap: `artifacts/oracle_family_decomposition_rel5_topup_uniform/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_decomposition_rel5_topup_uniform/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_decomposition_rel5_topup_uniform/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_decomposition_rel5_topup_uniform/pairwise_crossover.png`

## Pairwise Crossover

- Smaller model: `gpt-5.3-codex-spark`
- Larger model: `gpt-5.3-codex`
- Cost ratio: `4.154010`
- Aggregate crossover depth: `4096.000000`

## Pairwise Terms

- Baseline model: `gpt-5.3-codex-spark`
- Comparison model: `gpt-5.3-codex`
- Cost term: `-1.424074`
- Competence term: `6.816595`
