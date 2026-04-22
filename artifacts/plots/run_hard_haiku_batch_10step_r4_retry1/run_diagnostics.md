# Run Diagnostics

Run: `hard_haiku_batch_10step_r4_retry1`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.1107423890825674` | `0.1107423890825674` | `0.0` | `0.0` | `0.13617559999999998` | `78172` |
| `1` | `topk` | `topk` | `micro` | `0.1970589460600577` | `0.10790696752818758` | `0.08915197853187011` | `0.08915197853187011` | `0.22976635` | `156108` |
| `2` | `summaries` | `summaries` | `topk` | `inf` | `0.17581483776069518` | `1.0212441082993626` | `1.0212441082993626` | `0.1473708` | `83356` |
| `3` | `caching` | `caching` | `layout` | `inf` | `0.20906894394727316` | `1.0` | `1.0` | `0.17092305` | `91191` |
| `4` | `layout` | `layout` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.16314035` | `88440` |
| `5` | `layout` | `layout` | `layout` | `0.9886260426128052` | `0.9886260426128052` | `0.0` | `0.0` | `0.16907669999999997` | `167624` |
| `6` | `layout` | `layout` | `layout` | `0.7612992626254728` | `0.7612992626254728` | `0.0` | `0.0` | `0.1475006` | `84243` |
| `7` | `layout` | `layout` | `indexing` | `inf` | `0.7574590664137383` | `1.0038401962117345` | `1.0038401962117345` | `0.19558530000000002` | `100369` |
| `8` | `layout` | `layout` | `layout` | `0.8571899011661437` | `0.8548213558952553` | `0.0` | `0.0` | `0.2166125` | `196578` |
| `9` | `layout` | `layout` | `layout` | `0.7691906031309182` | `0.7691906031309182` | `0.0` | `0.0` | `0.17891935` | `138088` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_10step_r4_retry1/single_mode_layout_trajectory.png`
