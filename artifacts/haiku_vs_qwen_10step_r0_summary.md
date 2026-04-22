# Haiku vs Qwen 10-Step R0 Summary

| model | steps | branches | sec/step | routing acc | mean regret | branch correct | best visible | best cf | input toks | output toks | cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| haiku_batch | 10 | 60 | 302.7 | 0.20 | 0.4085 | 0.83 | 0.1860 | 0.1090 | 1062396 | 266434 | 1.940 |
| qwen_direct | 10 | 60 | 181.0 | 0.20 | 0.0140 | 1.00 | 0.9708 | 0.9690 | 1094080 | 17270 | 0.000 |

## haiku_batch

- Selected counts: `{'layout': 6, 'indexing': 1, 'topk': 1, 'caching': 1, 'summaries': 1, 'micro': 0}`
- Best-mode counts: `{'layout': 3, 'indexing': 2, 'topk': 3, 'caching': 0, 'summaries': 1, 'micro': 1}`
- Routing correct/incorrect: `2` / `8`

| step | selected | best | selected loss | best loss | regret |
|---:|---|---|---:|---:|---:|
| 0 | indexing | layout | inf | 0.3430 | 1.6487 |
| 1 | layout | indexing | 0.1860 | 0.1834 | 0.0000 |
| 2 | topk | micro | 0.2522 | 0.1090 | 0.1432 |
| 3 | summaries | topk | 1.4177 | 0.2429 | 1.1748 |
| 4 | caching | summaries | 1.4208 | 1.4052 | 0.0156 |
| 5 | layout | layout | 1.3146 | 1.3146 | 0.0000 |
| 6 | layout | indexing | 1.3240 | 1.2674 | 0.0566 |
| 7 | layout | layout | 1.2801 | 1.2801 | 0.0000 |
| 8 | layout | topk | 1.2801 | 1.2565 | 0.0235 |
| 9 | layout | topk | inf | 1.2579 | 1.0222 |

## qwen_direct

- Selected counts: `{'layout': 9, 'indexing': 1, 'topk': 0, 'caching': 0, 'summaries': 0, 'micro': 0}`
- Best-mode counts: `{'layout': 2, 'indexing': 1, 'topk': 1, 'caching': 2, 'summaries': 0, 'micro': 4}`
- Routing correct/incorrect: `2` / `8`

| step | selected | best | selected loss | best loss | regret |
|---:|---|---|---:|---:|---:|
| 0 | layout | caching | 0.9723 | 0.9697 | 0.0026 |
| 1 | layout | micro | 0.9960 | 0.9802 | 0.0158 |
| 2 | indexing | topk | 0.9748 | 0.9730 | 0.0018 |
| 3 | layout | micro | 1.0319 | 0.9805 | 0.0514 |
| 4 | layout | layout | 0.9708 | 0.9708 | 0.0000 |
| 5 | layout | indexing | 0.9960 | 0.9948 | 0.0013 |
| 6 | layout | caching | 0.9990 | 0.9703 | 0.0287 |
| 7 | layout | layout | 0.9939 | 0.9939 | 0.0000 |
| 8 | layout | micro | 0.9789 | 0.9690 | 0.0099 |
| 9 | layout | micro | 0.9974 | 0.9693 | 0.0281 |
