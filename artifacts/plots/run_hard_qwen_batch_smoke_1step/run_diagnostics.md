# Run Diagnostics

Run: `hard_qwen_batch_smoke_1step`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `topk` | `1.0005345479179988` | `0.9999240408742531` | `0.0006105070437456561` | `0.0006105070437456561` | `None` | `13387` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_batch_smoke_1step/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_batch_smoke_1step/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_batch_smoke_1step/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_batch_smoke_1step/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_batch_smoke_1step/single_mode_indexing_trajectory.png`
