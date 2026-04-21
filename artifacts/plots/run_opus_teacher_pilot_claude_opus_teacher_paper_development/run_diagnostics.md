# Run Diagnostics

Run: `opus_teacher_pilot_claude_opus_teacher_paper_development`
Profile: `paper_development`
Model: `opus`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.855458450330752` | `0.855458450330752` | `0.0` | `0.0` | `1.6530162500000003` | `301325` |
| `1` | `indexing` | `indexing` | `caching` | `0.9725707595926503` | `0.923306297932887` | `0.04926446165976328` | `0.04926446165976328` | `1.7044645` | `305504` |
| `2` | `topk` | `topk` | `indexing` | `1.1750108151317746` | `0.8198872164424283` | `0.3551235986893463` | `0.3551235986893463` | `1.2838150000000002` | `227630` |

## Plots
- mode_probs: `artifacts/plots/run_opus_teacher_pilot_claude_opus_teacher_paper_development/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_opus_teacher_pilot_claude_opus_teacher_paper_development/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_opus_teacher_pilot_claude_opus_teacher_paper_development/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_opus_teacher_pilot_claude_opus_teacher_paper_development/cost_per_step.png`
