# Task-Mode Robustness

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Target Wilson half-width: `0.15`
- Smoothed p_min: `0.083333`
- Bernstein per-mode target: `2524.05`
- Hoeffding per-mode target: `5048.09`
- Max additional trials needed in any current cell: `27`

## Current Cells

- `holdout / range_local_scans / gpt-5.3-codex`: `5/6` successes, Wilson=`[0.436, 0.970]`, additional-for-target=`15`
- `holdout / range_local_scans / gpt-5.3-codex-spark`: `10/10` successes, Wilson=`[0.722, 1.000]`, additional-for-target=`5`
- `holdout / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `holdout / topk_stress / gpt-5.3-codex-spark`: `0/10` successes, Wilson=`[0.000, 0.278]`, additional-for-target=`5`
- `pilot / range_local_scans / gpt-5.3-codex`: `6/6` successes, Wilson=`[0.610, 1.000]`, additional-for-target=`12`
- `pilot / range_local_scans / gpt-5.3-codex-spark`: `8/10` successes, Wilson=`[0.490, 0.943]`, additional-for-target=`16`
- `pilot / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `pilot / topk_stress / gpt-5.3-codex-spark`: `1/10` successes, Wilson=`[0.018, 0.404]`, additional-for-target=`8`
