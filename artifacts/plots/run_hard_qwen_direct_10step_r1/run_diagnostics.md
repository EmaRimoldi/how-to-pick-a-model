# Run Diagnostics

Run: `hard_qwen_direct_10step_r1`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `indexing` | `0.9714003398911016` | `0.9703883945456835` | `0.0010119453454181526` | `0.0010119453454181526` | `None` | `51403` |
| `1` | `layout` | `layout` | `caching` | `1.0296772818177002` | `0.9897288321308501` | `0.039948449686850185` | `0.039948449686850185` | `None` | `61613` |
| `2` | `layout` | `layout` | `micro` | `1.0942769110160577` | `0.9807013880348081` | `0.11357552298124962` | `0.11357552298124962` | `None` | `77825` |
| `3` | `layout` | `layout` | `indexing` | `0.9754718320760719` | `0.9717631828928385` | `0.0037086491832334367` | `0.0037086491832334367` | `None` | `104621` |
| `4` | `layout` | `layout` | `micro` | `0.9961037535501726` | `0.9874793977916053` | `0.008624355758567237` | `0.008624355758567237` | `None` | `95100` |
| `5` | `layout` | `layout` | `topk` | `0.9843561402227776` | `0.9797738784279377` | `0.0045822617948398925` | `0.0045822617948398925` | `None` | `114132` |
| `6` | `layout` | `layout` | `micro` | `1.0506692962093296` | `0.9694305173947567` | `0.08123877881457287` | `0.08123877881457287` | `None` | `113960` |
| `7` | `layout` | `layout` | `micro` | `0.9755584324563689` | `0.9691667954434003` | `0.006391637012968521` | `0.006391637012968521` | `None` | `153604` |
| `8` | `layout` | `layout` | `layout` | `0.9708210744348743` | `0.9708210744348743` | `0.0` | `0.0` | `None` | `146939` |
| `9` | `layout` | `layout` | `indexing` | `0.9711254529089908` | `0.9697130662377046` | `0.001412386671286181` | `0.001412386671286181` | `None` | `176386` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_direct_10step_r1/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_direct_10step_r1/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_direct_10step_r1/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_direct_10step_r1/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_direct_10step_r1/single_mode_layout_trajectory.png`
