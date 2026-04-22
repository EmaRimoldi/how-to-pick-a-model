# Run Diagnostics

Run: `paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_range_dev`
Profile: `hard_range_dev`
Model: `gpt-5.3-codex-spark`

| step | selected | top1 | verified best | selected loss | best loss | top1 regret | policy regret | cost usd | tokens |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `indexing` | `indexing` | `layout` | `0.9645190019277455` | `0.29685298185165304` | `0.6676660200760925` | `0.6676660200760925` | `None` | `0` |
| `1` | `summaries` | `summaries` | `indexing` | `4.805780880616656` | `0.10870187487248154` | `4.6970790057441745` | `4.6970790057441745` | `None` | `0` |
| `2` | `indexing` | `indexing` | `indexing` | `2.982786785914829` | `2.982786785914829` | `0.0` | `0.0` | `None` | `0` |

## Plots
- mode_probs: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_range_dev/mode_probs_by_step.png`
- loss_by_mode: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_range_dev/loss_by_step_by_mode.png`
- gain_heatmap: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_range_dev/gain_heatmap_by_step_mode.png`
- cost_per_step: `artifacts/plots/run_paper_dev_gpt53spark_r0_gpt_5_3_codex_spark_batch_strict_hard_range_dev/cost_per_step.png`
