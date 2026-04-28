# Oracle-Family Iterative Analysis

- Trajectories: `2`
- Completed trajectories: `0`
- Partial trajectories contributing prefixes: `2`
- Observed runtime hours: `0.020`
- Task modes: `topk_stress`
- Models: `gpt-5.3-codex-spark`
- Horizons analyzed: `1..4`

## Recommended Horizons

- `anytime::tau=0.000`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`
- `anytime::tau=0.050`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`
- `anytime::tau=0.100`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`
- `terminal::tau=0.000`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`
- `terminal::tau=0.050`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`
- `terminal::tau=0.100`: recommended horizon=`3`, best horizon=`3`, best oracle objective=`3.3631`

## Action-Routing Highlights

- `gpt-5.3-codex-spark`: highest mean routing mass on `topk` (0.331), strongest mean gain on `layout` (0.115)
