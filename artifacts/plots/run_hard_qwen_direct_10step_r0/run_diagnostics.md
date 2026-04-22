# Run Diagnostics

Run: `hard_qwen_direct_10step_r0`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `caching` | `0.9722705540288517` | `0.9697084369118346` | `0.0025621171170170376` | `0.0025621171170170376` | `None` | `51419` |
| `1` | `layout` | `layout` | `micro` | `0.9959826456900562` | `0.9802166181931613` | `0.01576602749689493` | `0.01576602749689493` | `None` | `61911` |
| `2` | `indexing` | `indexing` | `topk` | `0.9748261075346372` | `0.9730444811317752` | `0.0017816264028619466` | `0.0017816264028619466` | `None` | `90441` |
| `3` | `layout` | `layout` | `micro` | `1.0319017247890505` | `0.9804634754958591` | `0.05143824929319141` | `0.05143824929319141` | `None` | `91000` |
| `4` | `layout` | `layout` | `layout` | `0.970764917202432` | `0.970764917202432` | `0.0` | `0.0` | `None` | `100470` |
| `5` | `layout` | `layout` | `indexing` | `0.9960409029778915` | `0.9947770619385486` | `0.00126384103934285` | `0.00126384103934285` | `None` | `113978` |
| `6` | `layout` | `layout` | `caching` | `0.9989686227901724` | `0.9702729244199997` | `0.028695698370172718` | `0.028695698370172718` | `None` | `125741` |
| `7` | `layout` | `layout` | `layout` | `0.9938849415752257` | `0.9938849415752257` | `0.0` | `0.0` | `None` | `143012` |
| `8` | `layout` | `layout` | `micro` | `0.9788821545291838` | `0.968994120160391` | `0.00988803436879282` | `0.00988803436879282` | `None` | `159864` |
| `9` | `layout` | `layout` | `micro` | `0.9974387061117161` | `0.9693248356249435` | `0.028113870486772607` | `0.028113870486772607` | `None` | `173514` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_direct_10step_r0/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_direct_10step_r0/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_direct_10step_r0/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_direct_10step_r0/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_direct_10step_r0/single_mode_layout_trajectory.png`
