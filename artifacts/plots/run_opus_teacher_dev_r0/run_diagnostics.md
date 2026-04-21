# Run Diagnostics

Run: `opus_teacher_dev_r0`
Profile: `paper_development`
Model: `opus`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `indexing` | `1.0455316833075177` | `0.5467336985466943` | `0.4987979847608234` | `0.4987979847608234` | `1.7155750000000003` | `310508` |
| `1` | `indexing` | `indexing` | `indexing` | `0.7826559967599495` | `0.7826559967599495` | `0.0` | `0.0` | `1.7149727499999998` | `310156` |
| `2` | `topk` | `topk` | `layout` | `1.3120657704186152` | `0.7014455770193396` | `0.6106201933992755` | `0.6106201933992755` | `1.7410795` | `259378` |

## Plots
- mode_probs: `artifacts/plots/run_opus_teacher_dev_r0/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_opus_teacher_dev_r0/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_opus_teacher_dev_r0/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_opus_teacher_dev_r0/cost_per_step.png`
