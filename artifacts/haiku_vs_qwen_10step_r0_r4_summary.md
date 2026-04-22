# Haiku vs Qwen 10-Step R0-R4 Summary

Five validated hard-profile repeats per backend. Each run has 10 C(a) steps and 60 branch evaluations.

Best mode is computed as the declared branch mode with minimum finite verified `latent_loss` at that step. This preserves the six controlled branch identities even when the diff classifier infers a different structural mode.

Partial Haiku trials excluded from aggregate: `hard_haiku_batch_10step_r3`, `hard_haiku_batch_10step_r3_retry1`, and `hard_haiku_batch_10step_r4` because the Claude CLI exited with code 1 before 10 completed steps.

| backend | runs | steps | branches | sec/step mean | routing correct | routing acc | mean regret | branch correct | selected correct | best visible min | best cf min | total cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| haiku_batch | 5 | 50 | 300 | 242.1 | 10/50 | 0.20 | 0.5583 | 0.61 | 0.56 | 0.1107 | 0.1010 | 9.165 |
| qwen_direct | 5 | 50 | 300 | 203.9 | 12/50 | 0.24 | 0.0114 | 1.00 | 1.00 | 0.9708 | 0.9690 | 0.000 |

## haiku_batch

| run | sec/step | routing | mean regret | branch correct | selected correct | best visible | best cf | cost | selected counts | best counts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| hard_haiku_batch_10step_r0 | 302.7 | 2/10 | 0.3416 | 0.83 | 0.80 | 0.1860 | 0.1090 | 1.940 | `{'layout': 6, 'indexing': 1, 'topk': 1, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 3, 'indexing': 2, 'topk': 3, 'caching': 0, 'summaries': 1, 'micro': 1}` |
| hard_haiku_batch_10step_r1 | 254.3 | 2/10 | 0.6808 | 0.55 | 0.50 | 0.2702 | 0.1805 | 1.850 | `{'layout': 6, 'indexing': 0, 'topk': 2, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 3, 'indexing': 1, 'topk': 0, 'caching': 0, 'summaries': 2, 'micro': 3}` |
| hard_haiku_batch_10step_r2 | 197.0 | 1/10 | 0.5522 | 0.63 | 0.60 | 0.1652 | 0.1010 | 1.836 | `{'layout': 0, 'indexing': 6, 'topk': 2, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 0, 'indexing': 2, 'topk': 1, 'caching': 3, 'summaries': 0, 'micro': 2}` |
| hard_haiku_batch_10step_r3_retry2 | 213.1 | 1/10 | 0.8078 | 0.40 | 0.30 | 0.2881 | 0.1626 | 1.784 | `{'layout': 4, 'indexing': 1, 'topk': 2, 'caching': 1, 'summaries': 2, 'micro': 0}` | `{'layout': 3, 'indexing': 1, 'topk': 1, 'caching': 0, 'summaries': 0, 'micro': 0}` |
| hard_haiku_batch_10step_r4_retry1 | 243.5 | 4/10 | 0.4092 | 0.62 | 0.60 | 0.1107 | 0.1079 | 1.755 | `{'layout': 7, 'indexing': 0, 'topk': 1, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 5, 'indexing': 1, 'topk': 1, 'caching': 0, 'summaries': 0, 'micro': 2}` |

## qwen_direct

| run | sec/step | routing | mean regret | branch correct | selected correct | best visible | best cf | cost | selected counts | best counts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| hard_qwen_direct_10step_r0 | 181.0 | 2/10 | 0.0140 | 1.00 | 1.00 | 0.9708 | 0.9690 | 0.000 | `{'layout': 9, 'indexing': 1, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 2, 'indexing': 1, 'topk': 1, 'caching': 2, 'summaries': 0, 'micro': 4}` |
| hard_qwen_direct_10step_r1 | 183.2 | 1/10 | 0.0260 | 1.00 | 1.00 | 0.9708 | 0.9692 | 0.000 | `{'layout': 10, 'indexing': 0, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 1, 'indexing': 3, 'topk': 1, 'caching': 1, 'summaries': 0, 'micro': 4}` |
| hard_qwen_direct_10step_r2 | 200.9 | 1/10 | 0.0100 | 1.00 | 1.00 | 0.9939 | 0.9928 | 0.000 | `{'layout': 8, 'indexing': 0, 'topk': 2, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 2, 'indexing': 2, 'topk': 2, 'caching': 2, 'summaries': 1, 'micro': 1}` |
| hard_qwen_direct_10step_r3 | 227.3 | 4/10 | 0.0044 | 1.00 | 1.00 | 0.9987 | 0.9987 | 0.000 | `{'layout': 10, 'indexing': 0, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 4, 'indexing': 0, 'topk': 1, 'caching': 0, 'summaries': 2, 'micro': 3}` |
| hard_qwen_direct_10step_r4 | 227.1 | 4/10 | 0.0025 | 1.00 | 1.00 | 0.9954 | 0.9922 | 0.000 | `{'layout': 10, 'indexing': 0, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 4, 'indexing': 1, 'topk': 2, 'caching': 0, 'summaries': 1, 'micro': 2}` |
