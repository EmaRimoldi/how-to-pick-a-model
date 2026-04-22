# Haiku vs Qwen 10-Step R0-R2 Summary

Three validated hard-profile repeats per backend. Each run has 10 C(a) steps and 60 branch evaluations.

Best mode is computed as the declared branch mode with minimum verified `latent_loss` at that step. This preserves the six controlled branch identities even when the diff classifier infers a different structural mode.

| backend | runs | steps | branches | sec/step mean | routing correct | routing acc | mean regret | branch correct | selected correct | best visible min | best cf min | total cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| haiku_batch | 3 | 30 | 180 | 251.4 | 5/30 | 0.17 | 0.4248 | 0.67 | 0.63 | 0.1652 | 0.1010 | 5.626 |
| qwen_direct | 3 | 30 | 180 | 188.4 | 4/30 | 0.13 | 0.0167 | 1.00 | 1.00 | 0.9708 | 0.9690 | 0.000 |

## haiku_batch

| run | sec/step | routing | mean regret | branch correct | selected correct | best visible | best cf | cost | selected counts | best counts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| hard_haiku_batch_10step_r0 | 302.7 | 2/10 | 0.3416 | 0.83 | 0.80 | 0.1860 | 0.1090 | 1.940 | `{'layout': 6, 'indexing': 1, 'topk': 1, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 3, 'indexing': 2, 'topk': 3, 'caching': 0, 'summaries': 1, 'micro': 1}` |
| hard_haiku_batch_10step_r1 | 254.3 | 2/10 | 0.5808 | 0.55 | 0.50 | 0.2702 | 0.1805 | 1.850 | `{'layout': 6, 'indexing': 0, 'topk': 2, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 4, 'indexing': 1, 'topk': 0, 'caching': 0, 'summaries': 2, 'micro': 3}` |
| hard_haiku_batch_10step_r2 | 197.0 | 1/10 | 0.3522 | 0.63 | 0.60 | 0.1652 | 0.1010 | 1.836 | `{'layout': 0, 'indexing': 6, 'topk': 2, 'caching': 1, 'summaries': 1, 'micro': 0}` | `{'layout': 2, 'indexing': 2, 'topk': 1, 'caching': 3, 'summaries': 0, 'micro': 2}` |

## qwen_direct

| run | sec/step | routing | mean regret | branch correct | selected correct | best visible | best cf | cost | selected counts | best counts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| hard_qwen_direct_10step_r0 | 181.0 | 2/10 | 0.0140 | 1.00 | 1.00 | 0.9708 | 0.9690 | 0.000 | `{'layout': 9, 'indexing': 1, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 2, 'indexing': 1, 'topk': 1, 'caching': 2, 'summaries': 0, 'micro': 4}` |
| hard_qwen_direct_10step_r1 | 183.2 | 1/10 | 0.0260 | 1.00 | 1.00 | 0.9708 | 0.9692 | 0.000 | `{'layout': 10, 'indexing': 0, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 1, 'indexing': 3, 'topk': 1, 'caching': 1, 'summaries': 0, 'micro': 4}` |
| hard_qwen_direct_10step_r2 | 200.9 | 1/10 | 0.0100 | 1.00 | 1.00 | 0.9939 | 0.9928 | 0.000 | `{'layout': 8, 'indexing': 0, 'topk': 2, 'caching': 0, 'summaries': 0, 'micro': 0}` | `{'layout': 2, 'indexing': 2, 'topk': 2, 'caching': 2, 'summaries': 1, 'micro': 1}` |

