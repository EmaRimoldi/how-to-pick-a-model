# Oracle-Family Iterative Analysis

- Trajectories: `2`
- Completed trajectories: `0`
- Partial trajectories contributing prefixes: `2`
- Observed runtime hours: `0.043`
- Task modes: `topk_stress`
- Models: `gpt-5.3-codex-spark`
- Horizons analyzed: `1..3`

## Recommended Horizons

- `anytime::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`3.4258`
- `anytime::tau=0.050`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`17.2413`
- `anytime::tau=0.100`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`17.2413`
- `terminal::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`3.4258`
- `terminal::tau=0.050`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`17.2413`
- `terminal::tau=0.100`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`17.2413`

## Action-Routing Highlights

- `gpt-5.3-codex-spark`: highest mean routing mass on `topk` (0.318), strongest mean gain on `indexing` (0.476)
