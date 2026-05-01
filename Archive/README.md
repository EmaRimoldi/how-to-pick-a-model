# Archive

This directory contains benchmark surfaces and analysis code that are preserved for reference but are **not** part of the active NeurIPS_2026 mainline.

## Archived benchmark family

`stateful_query_engine/` contains the earlier QueryState / Stateful Query Engine benchmark, its configs, reports, and theorem-facing analysis utilities.

It was archived when the main paper and active framework were refocused on the AutoResearch CIFAR-10 task-level model-routing protocol.

### What stays active

The active benchmark surface now lives under:

- `benchmarks/autoresearch_cifar10/`
- `src/vao/analysis/autoresearch_*`
- `configs/autoresearch_cifar10_*`

If you need the older query-engine experiments for replication or historical comparison, use the archived paths explicitly rather than importing them into new runs.
