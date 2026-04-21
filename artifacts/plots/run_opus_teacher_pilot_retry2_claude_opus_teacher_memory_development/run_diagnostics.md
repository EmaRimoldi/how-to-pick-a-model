# Run Diagnostics

Run: `opus_teacher_pilot_retry2_claude_opus_teacher_memory_development`
Profile: `memory_development`
Model: `opus`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.6531563169239188` | `0.6531563169239188` | `0.0` | `0.0` | `1.59560475` | `298345` |
| `1` | `summaries` | `summaries` | `layout` | `4.037790429862385` | `0.6247162061075843` | `3.413074223754801` | `3.413074223754801` | `2.131672` | `335115` |
| `2` | `layout` | `layout` | `layout` | `1.0806902523524686` | `1.0806902523524686` | `0.0` | `0.0` | `1.9294444999999998` | `300000` |

## Plots
- mode_probs: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_opus_teacher_pilot_retry2_claude_opus_teacher_memory_development/cost_per_step.png`
