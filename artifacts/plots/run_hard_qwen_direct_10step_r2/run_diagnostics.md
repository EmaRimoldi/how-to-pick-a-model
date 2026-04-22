# Run Diagnostics

Run: `hard_qwen_direct_10step_r2`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `layout` | `0.9979408886610845` | `0.9979408886610845` | `0.0` | `0.0` | `None` | `54369` |
| `1` | `topk` | `topk` | `micro` | `1.0226902941459746` | `0.9962104036862767` | `0.026479890459697897` | `0.026479890459697897` | `None` | `52435` |
| `2` | `layout` | `layout` | `indexing` | `0.993916510981561` | `0.9928301212015875` | `0.00108638977997344` | `0.00108638977997344` | `None` | `80437` |
| `3` | `layout` | `layout` | `indexing` | `0.9984833760948584` | `0.9945566192097561` | `0.003926756885102245` | `0.003926756885102245` | `None` | `84420` |
| `4` | `layout` | `layout` | `summaries` | `1.0008584101924878` | `0.9952988136481236` | `0.00555959654436422` | `0.00555959654436422` | `None` | `101412` |
| `5` | `topk` | `topk` | `layout` | `0.9957150442800083` | `0.9951419050815306` | `0.00057313919847779` | `0.00057313919847779` | `None` | `120539` |
| `6` | `layout` | `layout` | `caching` | `1.3231921206170534` | `1.293417761268142` | `0.029774359348911483` | `0.029774359348911483` | `None` | `108524` |
| `7` | `layout` | `layout` | `topk` | `1.302564140569678` | `1.2931939050888799` | `0.009370235480798073` | `0.009370235480798073` | `None` | `155660` |
| `8` | `layout` | `layout` | `topk` | `1.315023189296982` | `1.3079491173863447` | `0.007074071910637247` | `0.007074071910637247` | `None` | `159425` |
| `9` | `layout` | `layout` | `caching` | `1.3092133444397607` | `1.2934270960627472` | `0.01578624837701348` | `0.01578624837701348` | `None` | `168647` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_direct_10step_r2/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_direct_10step_r2/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_direct_10step_r2/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_direct_10step_r2/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_direct_10step_r2/single_mode_layout_trajectory.png`
