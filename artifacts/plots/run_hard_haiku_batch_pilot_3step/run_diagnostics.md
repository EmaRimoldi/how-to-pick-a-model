# Run Diagnostics

Run: `hard_haiku_batch_pilot_3step`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.32253722935593165` | `0.32253722935593165` | `0.0` | `0.0` | `0.27924545` | `223643` |
| `1` | `caching` | `caching` | `micro` | `0.30496058851131663` | `0.2784324758473186` | `0.026528112663998016` | `0.026528112663998016` | `0.13399534999999999` | `77708` |
| `2` | `summaries` | `summaries` | `micro` | `0.28242576429393895` | `0.28024672786820304` | `0.002179036425735914` | `0.002179036425735914` | `0.18695774999999998` | `137620` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_pilot_3step/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_pilot_3step/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_pilot_3step/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_pilot_3step/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_pilot_3step/single_mode_indexing_trajectory.png`
