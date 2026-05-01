# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.0`
Cost metric: `wall_seconds`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `3.787222`
- Pilot router holdout objective: `3.849587`
- Oracle router holdout objective: `3.805575`
- Pilot router information gain (nats): `0.000001`
- Pilot router mismatch to oracle (nats): `0.014377`

## Routing Triviality

- Pilot sufficient condition fires: `True`
- Pilot routing trivial empirically: `True`
- Holdout routing trivial empirically: `True`

## Figures

- success_heatmap: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p0/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p0/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p0/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p0/pairwise_crossover.png`

## Pairwise Crossover

- Smaller model: `gpt-5.3-codex-spark`
- Larger model: `gpt-5.3-codex`
- Cost ratio: `4.200348`
- Aggregate crossover depth: `1.000000`

## Pairwise Terms

- Baseline model: `gpt-5.3-codex-spark`
- Comparison model: `gpt-5.3-codex`
- Cost term: `-1.435167`
- Competence term: `-0.123969`
