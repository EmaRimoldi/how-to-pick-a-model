# Six natural initial repairs: difficulty screen not met

The prespecified initial-stage calibration completed all six requests. Qwen3-Coder-Next
(Parasail/BF16) fully repaired **4/6** adapted development bugs on both finite
suites. Two natural public-failing artifacts remain; the protocol required at
least three with multiple public failures. **The recovery stage is not run.**
No tasks are added to this closed cohort and no selector is trained.

| Initial result | Count |
| --- | ---: |
| Complete public-plus-evaluator repair | 4/6 |
| Valid JSON file artifact | 6/6 |
| Parseable Python | 5/6 |
| Public false acceptance | 0/6 |
| Missing outcome or new uncertain receipt | 0 |

The two failures have different characters. The timer response includes a stray
closing brace, so all public cases fail to load. The command-sequence response
fixes two previously failing empty-input cases but breaks three previously
passing cases involving ordering and access. This is a **post hoc descriptive
audit**, not proof of a unique cause or diagnostic effect. No candidate was
salvaged or rescored; four full repairs remains the result.

These data establish neither that traces help nor that they do not: no recovery
intervention was dispatched. They suggest this six-case pool supplies too few
natural failures for the planned comparison, and only one parseable failed
artifact in this draw. A new development design can inspect richer stateful
cases, but must be separately specified before models, retain every selected
case and preserve untouched evaluation groups. Repeating or expanding this
cohort after seeing the result is not the prespecified second stage.

## Accounting and independent verification

Actual new API spend: **$0.00297100** against a **$0.04** initial-stage limit.
Prior commitment **$0.20640271**, including thirteen old uncertain reserves, is
carried once: **$0.20937371 / $0.60** cumulative. Six requests and receipts
reconcile, all selected outcomes are present, and no new uncertainty arose.
No recovery allocation has been spent.

[Independent replay](reverification.json) reproduced the full analysis and
Markdown plus all **12 saved evaluations / 12 unique suites**, with zero
discrepancies. The [evidence manifest](evidence-manifest.json) records archive
SHA-256 `4a6566e915f14e736b241778253c2fdb963c09edc6076c0d941100eb76d403e9`.
Collector source: `4b744af9634dc4d7c1987722587ab44617c91990`; freeze:
`5e28b0afac79828ae77e4f10b0b8deb7820a68f6e0927a49b0ae64de0b73fc44`.
Exact public prompts, responses, receipts and inert source snapshots are retained.
The raw SSE byte stream is not archived; this is not wire-level replay.

## Reproduction

From the repository root, using fresh output paths:

```bash
uv run python scripts/verify_repair_contract_evidence.py \
  --input experiments/python-repair/checkpoint-environment/results/coverage-prefix-20261027 \
  --output runs/coverage-prefix-replay.json
uv run python experiments/python-repair/checkpoint-environment/results/coverage-prefix-20261027/reproduce_posthoc.py \
  --output runs/coverage-prefix-posthoc.json
```

The post hoc script verifies the archive hashes and reads JSON; it never executes
model code. Its output must equal `posthoc.json`. Full sandbox replay uses the
documented macOS isolation backend. These are exposed development tasks with
one initial draw each, not a population estimate, held-out evaluation, scaling
law or equal-total-resource policy result.
