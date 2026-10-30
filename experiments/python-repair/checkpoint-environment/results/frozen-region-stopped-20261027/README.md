# Frozen-region calibration: stopped and inconclusive

The separately frozen 32-request development calibration stopped on HTTP 429
at its twelfth admission: **11 responses, 1 uncertain request and 20 requests
never admitted**. All eight selected original-bug checkpoints and all 32 planned
cells remain in the report. No retry, resumption or successor is permitted by
this study's protocol. The collector exited with code 1; its terminal finalizer
completed without making model calls.

## What the data establish

| Arm | Responses / planned | Complete repairs | Missing outcomes | Public-score regressions |
| --- | ---: | ---: | ---: | ---: |
| Identical code and focused public feedback | 5/16 | 3 | 11 | 1 |
| Same core plus the frozen public runtime trace | 6/16 | 4 | 10 | 2 |

These counts are **not evidence of superiority**: the arm observations are
incomplete and unbalanced, with 21/32 outcomes missing. The prespecified primary
trace-minus-feedback bounds on the selected cells are **−62.5 to +68.75
percentage points**. These are possible binary-completion bounds, not confidence
intervals. Mean difference and bootstrap fields remain null. The complete-bank
development screen is **inconclusive_incomplete_bank**. No selector is fitted.

All eleven received outputs are usable. No observed public false acceptance is
recorded. Only one bug has all four scheduled responses, and the two new
stateful/recursive Scrapy tasks received no model calls before the stop. This
bank therefore cannot establish whether the revised trace retention helps those
more complex sources. It does not change any earlier study's results or gates.

## Verification and accounting

[Independent sandbox replay](reverification.json) reproduces the full analysis,
Markdown and **22 saved public/evaluator evaluations over 20 unique suites**,
with zero discrepancies. The exact eight acquired snapshots and projected
messages are verified without trace reexecution; stochastic intermediate values
are never replaced. The final [figure](figure/repair-information.png) was checked
against the report; its source and value/hash audit are retained in `figure/`.

- New known API charges: **$0.00690084**.
- Retained reserve for the HTTP 429 admission: **$0.01146880**; no zero-charge
  assumption or later credit snapshot settles this unknown request.
- New study commitment: **$0.01836964 / $0.38**.
- Historical commitment carried exactly once: **$0.20937371**.
- Cumulative commitment: **$0.22774335 / $0.60**, now including fourteen
  unresolved historical/current reserves in total. No cap was exceeded.

The eight cached diagnostic acquisitions used sixteen sandbox executions and
0.9227233328856528 recorded local seconds. Deployment projections charge the
trace acquisition per planned treatment draw; this is distinct from actual
research API spending. Shared source verification, public response tests,
evaluator-only research work and local seconds remain separate in analysis.json.
Same per-call limits do not establish equal total resources.

## Operational finding and remaining uncertainty

The error record establishes HTTP 429, before response headers completed,
without a generation receipt or Retry-After value. It does **not** identify
whether the cause was the platform, a provider or another rate-control layer.
A subsequent [read-only check](provider-readonly-check.json) found positive
account credit, enough remaining account/key capacity for $0.38, no exhausted
budget reported by GET /key, and the pinned endpoint still advertised. This
post-error observation does not prove the error's cause or authorize a retry.

OpenRouter documents separate credit, budget and rate controls, and exposes
current budget information through GET /api/v1/key. The error's own metadata is
needed to attribute a rejection; a positive balance alone does not do so.
[Official limits documentation](https://openrouter.ai/docs/api_reference/limits).
The retained error record has only code 429. No credential, account identifier,
key label or raw account balance is included in the public operational check.

### Read-only follow-up: known generation recovered

After the owner confirmed the browser account, both account-level logs over the
past month and the Default Workspace generation view over the past day remained
empty. A separate authenticated `GET /api/v1/generation` lookup recovered one
previously settled research generation: ID, Parasail provider, recorded cost and
server time (2026-10-27 07:02:55 UTC) match the saved evidence. Its model field uses
`qwen/qwen3-coder-next-2025-02-03`, which the contemporaneous public model catalog
identifies as the canonical slug of `qwen/qwen3-coder-next`. The initial literal
model-string mismatch is retained in the [sanitized check](provider-generation-check.json)
alongside the canonical reconciliation.

This verifies one existing receipt, not the entire bank or the uncertain
admission. Empty dashboard views do not negate saved receipts, identify the 429
cause or settle unknown costs. No settings, credentials, allocations or model
requests changed. The documented [generation metadata endpoint](https://openrouter.ai/docs/api/api-reference/generations/get-generation)
is read-only; the API lookup and public catalog lookup incur no model generation.

## Reproduction

Source commit: `2249591ca166c4a8ff49491585ca49ecbc72ecdb`.
Freeze: `f86dab464aa6e867036092e528f7f51c1957f78559f30263a5b4585e5da7cc93`.
Protocol: [FROZEN-REGION-PROTOCOL.md](../../FROZEN-REGION-PROTOCOL.md).
Allocation: [FROZEN-REGION-AUTHORIZED.json](../../FROZEN-REGION-AUTHORIZED.json).
The archive manifest supplies every file digest and the inert frozen sources.

From the repository root, with the native macOS sandbox and a fresh output:

```bash
uv run python scripts/verify_repair_contract_evidence.py \
  --input experiments/python-repair/checkpoint-environment/results/frozen-region-stopped-20261027 \
  --output /tmp/frozen-region-reverification.json
```

The report and figure can also be reproduced from their frozen inputs without
model calls. For the figure, copy `figure/plot_report.py.txt` to a fresh `.py`
path, verify its hash against `figure/figure-audit.json`, and run it with
`--input <this bundle>/analysis.json --output <fresh figure directory>`.
The SVG/PNG creation metadata can change; plotted values must match the audit.

This is exposed development evidence conditional on one acquisition per bug,
not a held-out evaluation, a scaling experiment, generated-failure recovery or
an equal-total-budget policy comparison. Next resolve the operational limitation
before defining another independent collection. The final acquisition selector
and its advantage over fixed policies remain unproved.
