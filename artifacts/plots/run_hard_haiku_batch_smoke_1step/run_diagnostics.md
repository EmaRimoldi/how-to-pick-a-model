# Run Diagnostics

Run: `hard_haiku_batch_smoke_1step`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `indexing` | `0.11013164681034375` | `0.11013164681034375` | `0.0` | `0.0` | `0.17126860000000002` | `87788` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_smoke_1step/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_smoke_1step/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_smoke_1step/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_smoke_1step/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_smoke_1step/single_mode_indexing_trajectory.png`
