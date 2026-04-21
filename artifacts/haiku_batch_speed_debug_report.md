# Haiku Batch Speed Debug Report

Question: does Haiku become faster when we stop making six separate candidate-generation calls per step?

Answer: yes on the 1-step smoke. The bottleneck was repeated Claude calls/context, not only full-file candidate text.

| protocol | steps | sec/step | USD/step | input tokens/step | output tokens/step | candidate error rate | verifier failure rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Haiku replacement smoke | 2 | 326.4 | 0.479 | 332968 | 48314 | 0.000 | 0.000 |
| Haiku structured edits, six calls | 1 | 480.4 | 0.629 | 331817 | 72751 | 0.000 | 0.000 |
| Haiku structured edits, one batch call | 1 | 132.7 | 0.179 | 64324 | 24346 | 0.167 | 0.167 |

Speedup:

- vs structured per-mode calls: 3.62x
- vs replacement smoke: 2.46x

Caveat: one `indexing` candidate in the batch smoke was rejected by source safety validation and logged as an explicit no-op. The run passes protocol validation, but this path should get a prompt/repair pass before scaling.

Run: `runs/phase3_real_backend/haiku_structured_batch_smoke/haiku_structured_batch_speed`
