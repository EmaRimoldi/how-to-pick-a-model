# Run Diagnostics

Run: `hard_haiku_batch_10step_r1`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.3884408564170229` | `0.3884408564170229` | `0.0` | `0.0` | `0.18936540000000002` | `95432` |
| `1` | `layout` | `layout` | `indexing` | `0.2702468139537497` | `0.251555887414758` | `0.018690926538991737` | `0.018690926538991737` | `0.1782315` | `131333` |
| `2` | `summaries` | `summaries` | `micro` | `1.0079861303201496` | `0.18592781152702237` | `0.8220583187931272` | `0.8220583187931272` | `0.2107873` | `147518` |
| `3` | `topk` | `topk` | `summaries` | `inf` | `0.9727278289042525` | `1.0352583014158971` | `1.0352583014158971` | `0.18560945` | `136940` |
| `4` | `caching` | `caching` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.17106515` | `91841` |
| `5` | `layout` | `layout` | `micro` | `inf` | `1.001089105574848` | `1.0` | `1.0` | `0.20838545` | `104203` |
| `6` | `layout` | `layout` | `micro` | `inf` | `1.1551789601196918` | `1.0` | `1.0` | `0.16944770000000003` | `132549` |
| `7` | `layout` | `layout` | `summaries` | `inf` | `1.0023753164492906` | `1.0` | `1.0` | `0.11946255` | `76570` |
| `8` | `topk` | `topk` | `layout` | `1.1473790832741084` | `0.18052313810085666` | `0.0` | `0.0` | `0.20868525000000002` | `105265` |
| `9` | `layout` | `layout` | `layout` | `1.0048110655064406` | `1.0048110655064406` | `0.0` | `0.0` | `0.20935755` | `148693` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_10step_r1/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_10step_r1/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_10step_r1/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_10step_r1/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_10step_r1/single_mode_layout_trajectory.png`
