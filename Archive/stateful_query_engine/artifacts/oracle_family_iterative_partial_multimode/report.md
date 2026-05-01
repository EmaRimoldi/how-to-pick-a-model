# Oracle-Family Iterative Analysis

- Trajectories: `13`
- Completed trajectories: `5`
- Partial trajectories contributing prefixes: `8`
- Observed runtime hours: `0.596`
- Task modes: `negative_lookup_churn, topk_stress`
- Models: `gpt-5.3-codex, gpt-5.3-codex-spark`
- Horizons analyzed: `1..10`

## Recommended Horizons

- `anytime::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`2.7687`
- `anytime::tau=0.050`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`2.8923`
- `anytime::tau=0.100`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`2.8923`
- `terminal::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`2.7687`
- `terminal::tau=0.050`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`2.8923`
- `terminal::tau=0.100`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`2.8923`

## Action-Routing Highlights

- `gpt-5.3-codex`: highest mean routing mass on `topk` (0.241), strongest mean gain on `layout` (0.251)
- `gpt-5.3-codex-spark`: highest mean routing mass on `indexing` (0.237), strongest mean gain on `indexing` (0.133)
