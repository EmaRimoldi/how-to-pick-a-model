# Task-Mode Robustness

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Target Wilson half-width: `0.15`
- Smoothed p_min: `0.090909`
- Bernstein per-mode target: `2313.71`
- Hoeffding per-mode target: `4241.80`
- Max additional trials needed in any current cell: `27`

## Current Cells

- `holdout / range_local_scans / gpt-5.3-codex`: `4/5` successes, Wilson=`[0.376, 0.964]`, additional-for-target=`21`
- `holdout / range_local_scans / gpt-5.3-codex-spark`: `10/10` successes, Wilson=`[0.722, 1.000]`, additional-for-target=`5`
- `holdout / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `holdout / topk_stress / gpt-5.3-codex-spark`: `0/9` successes, Wilson=`[0.000, 0.299]`, additional-for-target=`6`
- `pilot / range_local_scans / gpt-5.3-codex`: `5/5` successes, Wilson=`[0.566, 1.000]`, additional-for-target=`16`
- `pilot / range_local_scans / gpt-5.3-codex-spark`: `8/10` successes, Wilson=`[0.490, 0.943]`, additional-for-target=`16`
- `pilot / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `pilot / topk_stress / gpt-5.3-codex-spark`: `1/8` successes, Wilson=`[0.022, 0.471]`, additional-for-target=`10`
