# Run Diagnostics

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_development`
Profile: `development`
Model: `opus`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `caching` | `0.9834796961719077` | `0.6323339867497109` | `0.3511457094221968` | `0.3511457094221968` | `1.5585925` | `294871` |
| `1` | `summaries` | `summaries` | `micro` | `5.1601290786073255` | `0.9426406044278975` | `4.217488474179428` | `4.217488474179428` | `1.873388` | `318886` |
| `2` | `topk` | `topk` | `micro` | `5.16567528748343` | `3.398745871693554` | `1.766929415789876` | `1.766929415789876` | `2.455712` | `364692` |

## Plots
- mode_probs: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_development/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_development/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_development/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_development/cost_per_step.png`
