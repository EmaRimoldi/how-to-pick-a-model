# Audited MBPP+ recovery evidence

All authorized collection ended on 2026-10-22. This is an **incomplete descriptive
bank**, not the originally planned complete confirmatory sample.

- 377 eligible tasks: 376 observed producer responses and one censored prefix.
- 96 selected public failures; 94 have all 30 model/context/draw observations.
- 2,878 observed recovery draws and two permanently censored solver cells.
- 288/288 valid, prespecified outcome-blind API forecasts, collected after recovery.
- $1.39600335 in cumulative known charges plus every unresolved reservation,
  within the existing $2 campaign ceiling; no continuation receives a new budget.

The first 96 selected failures precede the missing prefix. The two solver cells
are a 27B code-only third draw on `Mbpp/426` and a 9B fresh first draw on
`Mbpp/84`. No observed or uncertain request was repeated. Raw journals preserve
both authorized recovery segments, their earlier lineages, stop summaries and
preflights. Read the [protocol and amendments](../../PROTOCOL.md).

The [full report](report.md) gives the fixed primary, all context comparisons,
policy controls, forecast scores and accounting. [analysis.json](analysis.json)
also contains draw-rotation sensitivities, all budgets/actions, token receipts,
public false positives, feature shifts and exploratory noise-adjusted benefit
variance. Complete-case intervals are descriptive. The all-96-state utility
bounds retain the missing cases and are **not confidence intervals**.

Reproduce from the repository root, with a fresh output path:

```bash
uv run python scripts/analyze_recovery_transfer.py \
  --input experiments/mbpp-plus/context-value-transfer/results/replication-20261022 \
  --forecasts experiments/mbpp-plus/context-value-transfer/results/replication-20261022/semantic-control \
  --expected-analysis experiments/mbpp-plus/context-value-transfer/results/replication-20261022/analysis.json \
  --output runs/mbpp-reanalysis
```

This audits checksums, prompt projections, frozen predictions, every admission,
receipt, missing response and continuation allowlist. It reproduces statistics
and finite rollouts without model calls, candidate execution, credentials or
GPUs. Scalar agreement permits only floating-point roundoff; figure metadata
need not be byte-identical across machines.

[Source provenance](provenance/collector-sources/source-map.json) preserves 17
exact Git source blobs, 11 recorded hash anchors and 28 checks of unchanged
shared helpers. Python snapshots use `.py.txt` to remain inert evidence.
The original experimental manifest is preserved byte for byte; actual later
collectors have separate provenance. Curation tools are in the bundle's
`source/` directory. Benchmark attribution remains in the [bundle README](../../README.md).
