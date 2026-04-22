# Run Diagnostics

Run: `hard_haiku_batch_10step_r2`
Profile: `hard_optimization`
Model: `haiku`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `indexing` | `0.1652382113439318` | `0.1652382113439318` | `0.0` | `0.0` | `0.12717295` | `81378` |
| `1` | `caching` | `caching` | `micro` | `0.16719990680020785` | `0.10096813188548197` | `0.06623177491472589` | `0.06623177491472589` | `0.20839434999999998` | `146188` |
| `2` | `indexing` | `indexing` | `micro` | `0.23482323804838412` | `0.2061332680927167` | `0.028689969955667416` | `0.028689969955667416` | `0.26761044999999994` | `215928` |
| `3` | `summaries` | `summaries` | `indexing` | `1.4827818214016237` | `0.22474911597131678` | `1.2580327054303069` | `1.2580327054303069` | `0.17265225` | `91325` |
| `4` | `indexing` | `indexing` | `caching` | `1.4954590247616784` | `1.414014880513064` | `0.08144414424861446` | `0.08144414424861446` | `0.3079417` | `281223` |
| `5` | `topk` | `topk` | `caching` | `1.4946342898315121` | `1.4074714676054136` | `0.0871628222260985` | `0.0871628222260985` | `0.1471608` | `84355` |
| `6` | `topk` | `topk` | `caching` | `inf` | `1.4879392248307721` | `1.00669506500074` | `1.00669506500074` | `0.16746495` | `92483` |
| `7` | `indexing` | `indexing` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.17792669999999997` | `138024` |
| `8` | `indexing` | `indexing` | `topk` | `inf` | `1.587635752455387` | `1.0` | `1.0` | `0.12971985` | `81040` |
| `9` | `indexing` | `indexing` | `layout` | `inf` | `inf` | `0.0` | `0.0` | `0.1298289` | `81362` |

## Plots
- mode_probs: `artifacts/plots/run_hard_haiku_batch_10step_r2/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_haiku_batch_10step_r2/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_haiku_batch_10step_r2/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_haiku_batch_10step_r2/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_haiku_batch_10step_r2/single_mode_layout_trajectory.png`
