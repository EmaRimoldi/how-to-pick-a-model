# Oracle-Family Iterative Analysis

- Trajectories: `6`
- Completed trajectories: `3`
- Partial trajectories contributing prefixes: `3`
- Observed runtime hours: `0.403`
- Task modes: `topk_stress`
- Models: `gpt-5.3-codex, gpt-5.3-codex-spark`
- Horizons analyzed: `1..10`

## Recommended Horizons

- `anytime::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`2.8917`
- `anytime::tau=0.050`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`3.4596`
- `anytime::tau=0.100`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`3.4596`
- `terminal::tau=0.000`: recommended horizon=`1`, best horizon=`1`, best oracle objective=`2.8917`
- `terminal::tau=0.050`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`3.4596`
- `terminal::tau=0.100`: recommended horizon=`2`, best horizon=`2`, best oracle objective=`3.4596`

## Action-Routing Highlights

- `gpt-5.3-codex`: highest mean routing mass on `topk` (0.296), strongest mean gain on `layout` (0.280)
- `gpt-5.3-codex-spark`: highest mean routing mass on `topk` (0.283), strongest mean gain on `indexing` (0.221)
