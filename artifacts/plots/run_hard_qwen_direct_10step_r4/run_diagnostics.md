# Run Diagnostics

Run: `hard_qwen_direct_10step_r4`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.9954825132414364` | `0.9954825132414364` | `0.0` | `0.0` | `None` | `52484` |
| `1` | `layout` | `layout` | `layout` | `0.9962798858598568` | `0.9962798858598568` | `0.0` | `0.0` | `None` | `60728` |
| `2` | `layout` | `layout` | `micro` | `0.9985681520569236` | `0.9957969461234772` | `0.0027712059334463746` | `0.0027712059334463746` | `None` | `86327` |
| `3` | `layout` | `layout` | `layout` | `0.9957602633776372` | `0.9957602633776372` | `0.0` | `0.0` | `None` | `95692` |
| `4` | `layout` | `layout` | `topk` | `0.9972015491437447` | `0.9948102667661597` | `0.0023912823775850134` | `0.0023912823775850134` | `None` | `105377` |
| `5` | `layout` | `layout` | `layout` | `0.9954417208954117` | `0.9954417208954117` | `0.0` | `0.0` | `None` | `107870` |
| `6` | `layout` | `layout` | `micro` | `0.9989495460187369` | `0.9948288735820522` | `0.00412067243668468` | `0.00412067243668468` | `None` | `126742` |
| `7` | `layout` | `layout` | `summaries` | `1.002068224013208` | `0.9958217876254365` | `0.006246436387771448` | `0.006246436387771448` | `None` | `148811` |
| `8` | `layout` | `layout` | `topk` | `1.0015632269241852` | `0.9921812378841993` | `0.009381989039985883` | `0.009381989039985883` | `None` | `161978` |
| `9` | `layout` | `layout` | `indexing` | `0.9968023225953266` | `0.9962716501489522` | `0.0005306724463743917` | `0.0005306724463743917` | `None` | `144266` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_direct_10step_r4/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_direct_10step_r4/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_direct_10step_r4/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_direct_10step_r4/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_direct_10step_r4/single_mode_layout_trajectory.png`
