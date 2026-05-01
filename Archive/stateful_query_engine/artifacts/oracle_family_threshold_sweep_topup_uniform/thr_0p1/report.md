# Oracle-Family Task-Mode Decomposition

Success mode: `relative_improvement`
Success threshold: `0.95`
Improvement threshold: `0.1`
Cost metric: `wall_seconds`
Task-mode priors: `uniform`

## Holdout Summary

- Single-best pilot model: `gpt-5.3-codex-spark`
- Single-best holdout objective: `10.695749`
- Pilot router holdout objective: `4.906274`
- Oracle router holdout objective: `4.541397`
- Pilot router information gain (nats): `0.485848`
- Pilot router mismatch to oracle (nats): `0.039253`

## Routing Triviality

- Pilot sufficient condition fires: `False`
- Pilot routing trivial empirically: `False`
- Holdout routing trivial empirically: `False`

## Figures

- success_heatmap: `artifacts/oracle_family_threshold_sweep_topup_uniform/thr_0p1/success_prob_heatmap.png`
- rho_heatmap: `artifacts/oracle_family_threshold_sweep_topup_uniform/thr_0p1/cost_adjusted_score_heatmap.png`
- router_choices: `artifacts/oracle_family_threshold_sweep_topup_uniform/thr_0p1/router_choice_heatmap.png`
- pairwise_crossover: `artifacts/oracle_family_threshold_sweep_topup_uniform/thr_0p1/pairwise_crossover.png`

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
