# Oracle-Family Iterative Analysis

- Trajectories: `20`
- Completed runtime hours: `0.542`
- Task modes: `range_local_scans, topk_stress`
- Models: `gpt-5.3-codex, gpt-5.3-codex-spark`
- Horizons analyzed: `1..1`

## Recommended Horizons

- `anytime::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`3.7678`
- `anytime::tau=0.050`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`4.5163`
- `terminal::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`3.7678`
- `terminal::tau=0.050`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`4.5163`

## Action-Routing Highlights

- `gpt-5.3-codex`: highest mean routing mass on `indexing` (0.254), strongest mean gain on `indexing` (0.794)
- `gpt-5.3-codex-spark`: highest mean routing mass on `indexing` (0.239), strongest mean gain on `indexing` (0.748)
