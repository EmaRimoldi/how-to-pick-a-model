# Run Diagnostics

Run: `paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_balanced_dev`
Profile: `hard_balanced_dev`
Model: `gpt-5.3-codex-spark`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `layout` | `layout` | `indexing` | `0.30926945207182865` | `0.21919719986397432` | `0.09007225220785431` | `0.09007225220785431` | `None` | `0` |
| `1` | `caching` | `caching` | `indexing` | `0.3369264557935959` | `0.14995017531878163` | `0.1869762804748143` | `0.1869762804748143` | `None` | `0` |
| `2` | `indexing` | `indexing` | `micro` | `inf` | `0.28592134865386143` | `1.0510051071397344` | `1.0510051071397344` | `None` | `0` |

## Plots
- mode_probs: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_balanced_dev/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_balanced_dev/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_balanced_dev/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_balanced_dev/cost_per_step.png`
