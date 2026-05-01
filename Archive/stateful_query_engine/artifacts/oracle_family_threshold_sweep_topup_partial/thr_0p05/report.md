# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.05`
Cost metric: `wall_seconds`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `9.927449`
- Pilot router holdout objective: `4.941485`
- Oracle router holdout objective: `4.457626`
- Pilot router information gain (nats): `0.462336`
- Pilot router mismatch to oracle (nats): `0.047796`

## Routing Triviality

- Pilot sufficient condition fires: `False`
- Pilot routing trivial empirically: `False`
- Holdout routing trivial empirically: `False`

## Figures

- success_heatmap: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p05/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p05/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p05/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_threshold_sweep_topup_partial/thr_0p05/pairwise_crossover.png`

## Pairwise Crossover

- Smaller model: `gpt-5.3-codex-spark`
- Larger model: `gpt-5.3-codex`
- Cost ratio: `4.200348`
- Aggregate crossover depth: `4096.000000`

## Pairwise Terms

- Baseline model: `gpt-5.3-codex-spark`
- Comparison model: `gpt-5.3-codex`
- Cost term: `-1.435167`
- Competence term: `6.016258`
