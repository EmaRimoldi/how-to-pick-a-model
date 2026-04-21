# Run Diagnostics

Run: `hard_local_dev_2step_calibration`
Profile: `hard_optimization`
Model: `local-stub-v1`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `indexing` | `0.1047408737177043` | `0.1047408737177043` | `0.0` | `0.0` | `None` | `0` |
| `1` | `caching` | `caching` | `indexing` | `0.13263317922409945` | `0.105994942610374` | `0.026638236613725455` | `0.026638236613725455` | `None` | `0` |

## Plots
- mode_probs: `artifacts/plots/run_hard_local_dev_2step_calibration/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_local_dev_2step_calibration/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_local_dev_2step_calibration/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_local_dev_2step_calibration/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_local_dev_2step_calibration/single_mode_indexing_trajectory.png`
