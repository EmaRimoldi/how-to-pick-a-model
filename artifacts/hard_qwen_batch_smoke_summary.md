# Hard Qwen Batch Smoke Summary

- Run: `runs/hard_profile/qwen_batch_smoke/hard_qwen_batch_smoke_1step`
- Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- Steps: `1`
- Branch evaluations: `6`
- Wall-clock: `240.91s` (`240.91s/step`)
- Input/output tokens: `11658` / `1729`
- Candidate generation path: `batched_fallback_per_mode_structured_edits`
- Selected mode: `layout`
- Best counterfactual mode: `topk`
- Routing regret: `0.000611`

## Branches

| mode | correct | loss | gain | promoted | failures |
|---|---:|---:|---:|---:|---|
| layout | True | 1.000535 | 0.000704 | True |  |
| indexing | True | 1.003256 | -0.002018 | False |  |
| topk | True | 0.999924 | 0.001314 | False |  |
| caching | True | 1.001766 | -0.000528 | False |  |
| summaries | True | 1.007299 | -0.006061 | False |  |
| micro | True | 1.008506 | -0.007268 | False |  |
