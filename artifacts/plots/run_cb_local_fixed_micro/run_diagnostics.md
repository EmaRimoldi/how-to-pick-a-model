# Run Diagnostics

Run: `cb_local_fixed_micro`
Profile: `paper_development`
Model: `local-stub-v1`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `micro` | `indexing` | `indexing` | `0.8677997764862695` | `0.4820986539802012` | `0.0` | `0.38570112250606825` | `None` | `0` |
| `1` | `micro` | `caching` | `indexing` | `0.8584921018023087` | `0.481172646924523` | `1.278997295890621` | `0.37731945487778573` | `None` | `0` |

## Plots
- mode_probs: `artifacts/plots/run_cb_local_fixed_micro/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_cb_local_fixed_micro/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_cb_local_fixed_micro/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_cb_local_fixed_micro/cost_per_step.png`
- pre_post_mode_probs: `artifacts/plots/run_cb_local_fixed_micro/pre_post_mode_probs_by_step.png`
- single_mode: `artifacts/plots/run_cb_local_fixed_micro/single_mode_micro_trajectory.png`
