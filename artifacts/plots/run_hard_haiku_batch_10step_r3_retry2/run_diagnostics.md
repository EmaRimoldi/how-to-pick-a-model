# Run Diagnostics

Run: `hard_haiku_batch_10step_r3_retry2`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.2881984524885073` | `0.2881984524885073` | `0.0` | `0.0` | `0.20908385000000002` | `153762` |
| `1` | `summaries` | `summaries` | `indexing` | `0.2881105486175005` | `0.17361208378222426` | `0.11449846483527626` | `0.11449846483527626` | `0.2099897` | `144754` |
| `2` | `summaries` | `summaries` | `layout` | `1.1257521358839582` | `0.16264770972626433` | `0.9631044261576939` | `0.9631044261576939` | `0.1537847` | `84518` |
| `3` | `topk` | `topk` | `layout` | `inf` | `0.9702701246868237` | `1.1554820111971345` | `1.1554820111971345` | `0.15071554999999998` | `84167` |
| `4` | `caching` | `caching` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.13498380000000001` | `79183` |
| `5` | `layout` | `layout` | `topk` | `inf` | `1.1503375048221973` | `1.0` | `1.0` | `0.2360189` | `193063` |
| `6` | `indexing` | `indexing` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.15443645` | `87533` |
| `7` | `layout` | `layout` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.12989575` | `80052` |
| `8` | `layout` | `layout` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.26088115` | `170934` |
| `9` | `topk` | `topk` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.1439859` | `121128` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_10step_r3_retry2/single_mode_layout_trajectory.png`
