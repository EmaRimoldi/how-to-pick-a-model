# Run Diagnostics

Run: `hard_qwen_direct_10step_r3`
Profile: `hard_optimization`
Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `micro` | `1.0199735698413406` | `1.0131149850549643` | `0.006858584786376243` | `0.006858584786376243` | `None` | `45324` |
| `1` | `layout` | `layout` | `summaries` | `1.020415501298179` | `1.0004745955482743` | `0.019940905749904703` | `0.019940905749904703` | `None` | `63777` |
| `2` | `layout` | `layout` | `summaries` | `1.0015100105449681` | `0.9998616028792389` | `0.0016484076657292679` | `0.0016484076657292679` | `None` | `74495` |
| `3` | `layout` | `layout` | `layout` | `1.0016245601204146` | `1.0016245601204146` | `0.0` | `0.0` | `None` | `89198` |
| `4` | `layout` | `layout` | `layout` | `1.0047325668145994` | `1.0047325668145994` | `0.0` | `0.0` | `None` | `101335` |
| `5` | `layout` | `layout` | `micro` | `1.0119697286874556` | `1.0015396336837785` | `0.010430095003677087` | `0.010430095003677087` | `None` | `98863` |
| `6` | `layout` | `layout` | `layout` | `0.99946169933389` | `0.99946169933389` | `0.0` | `0.0` | `None` | `95422` |
| `7` | `layout` | `layout` | `layout` | `0.9987153801354273` | `0.9987153801354273` | `0.0` | `0.0` | `None` | `139719` |
| `8` | `layout` | `layout` | `topk` | `1.0053822197263573` | `1.0010426809401796` | `0.004339538786177766` | `0.004339538786177766` | `None` | `125984` |
| `9` | `layout` | `layout` | `micro` | `1.0009969765163065` | `1.0002941338089508` | `0.0007028427073556553` | `0.0007028427073556553` | `None` | `146064` |

## Plots
- mode_probs: `artifacts/plots/run_hard_qwen_direct_10step_r3/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_hard_qwen_direct_10step_r3/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_hard_qwen_direct_10step_r3/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_hard_qwen_direct_10step_r3/cost_per_step.png`
- single_mode: `artifacts/plots/run_hard_qwen_direct_10step_r3/single_mode_layout_trajectory.png`
