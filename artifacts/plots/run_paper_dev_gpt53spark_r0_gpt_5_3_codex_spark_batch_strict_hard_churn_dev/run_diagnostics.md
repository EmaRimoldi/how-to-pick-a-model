# Run Diagnostics

Run: `paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_churn_dev`
Profile: `hard_churn_dev`
Model: `gpt-5.3-codex-spark`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `indexing` | `0.17839108987811567` | `0.17839108987811567` | `0.0` | `0.0` | `None` | `0` |
| `1` | `indexing` | `indexing` | `layout` | `0.3260661100012075` | `0.16692744185323746` | `0.15913866814797004` | `0.15913866814797004` | `None` | `0` |
| `2` | `topk` | `topk` | `micro` | `0.3334336266168641` | `0.11457330393117555` | `0.21886032268568856` | `0.21886032268568856` | `None` | `0` |

## Plots
- mode_probs: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_churn_dev/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_churn_dev/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_churn_dev/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_churn_dev/cost_per_step.png`
