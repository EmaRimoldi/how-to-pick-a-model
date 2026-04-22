# Run Diagnostics

Run: `hard_haiku_batch_10step_r0`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `layout` | `inf` | `0.3430285069273253` | `1.6486991043115375` | `1.6486991043115375` | `0.17949104999999999` | `90272` |
| `1` | `layout` | `layout` | `layout` | `0.1859642773846367` | `0.18338076703359238` | `0.0` | `0.0` | `0.25803645000000003` | `164098` |
| `2` | `topk` | `topk` | `micro` | `0.2522185429866172` | `0.10904997342664634` | `0.14316856955997087` | `0.14316856955997087` | `0.2762131` | `256507` |
| `3` | `summaries` | `summaries` | `topk` | `1.417659767981672` | `0.24286714267867268` | `1.1747926253029992` | `1.1747926253029992` | `0.1516767` | `85315` |
| `4` | `caching` | `caching` | `summaries` | `1.4208081646627848` | `1.4052495218918881` | `0.015558642770896691` | `0.015558642770896691` | `0.1744994` | `169231` |
| `5` | `layout` | `layout` | `layout` | `1.3146099034179448` | `1.3146099034179448` | `0.0` | `0.0` | `0.17235125` | `130907` |
| `6` | `layout` | `layout` | `indexing` | `1.324012248169827` | `1.2673888823477957` | `0.056623365822031424` | `0.056623365822031424` | `0.16223285000000004` | `89336` |
| `7` | `layout` | `layout` | `layout` | `1.2801122619226417` | `1.2801122619226417` | `0.0` | `0.0` | `0.19174750000000002` | `143970` |
| `8` | `layout` | `layout` | `topk` | `1.2800623856711573` | `1.2565350828847595` | `0.023527302786397808` | `0.023527302786397808` | `0.15286529999999998` | `88485` |
| `9` | `layout` | `layout` | `topk` | `inf` | `1.2578762593365844` | `1.0221861263345728` | `1.0221861263345728` | `0.22060075` | `110709` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_10step_r0/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_10step_r0/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_10step_r0/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_10step_r0/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_10step_r0/single_mode_layout_trajectory.png`
