# Task-Mode Robustness

- Success mode: `relative_improvement`
- Success threshold: `0.95`
- Improvement threshold: `0.05`
- Target Wilson half-width: `0.15`
- Smoothed p_min: `0.200000`
- Bernstein per-mode target: `1051.69`
- Hoeffding per-mode target: `876.41`
- Max additional trials needed in any current cell: `33`

## Current Cells

- `holdout / range_local_scans / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `holdout / range_local_scans / gpt-5.3-codex-spark`: `3/3` successes, Wilson=`[0.439, 1.000]`, additional-for-target=`23`
- `holdout / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `holdout / topk_stress / gpt-5.3-codex-spark`: `0/3` successes, Wilson=`[0.000, 0.561]`, additional-for-target=`23`
- `pilot / range_local_scans / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `pilot / range_local_scans / gpt-5.3-codex-spark`: `3/3` successes, Wilson=`[0.439, 1.000]`, additional-for-target=`23`
- `pilot / topk_stress / gpt-5.3-codex`: `2/2` successes, Wilson=`[0.342, 1.000]`, additional-for-target=`27`
- `pilot / topk_stress / gpt-5.3-codex-spark`: `1/3` successes, Wilson=`[0.061, 0.792]`, additional-for-target=`33`
