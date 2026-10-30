# Public-trace probe: first-request interruption

**No model responses were received. This is operational evidence, not a result
about execution traces or repair ability.** The [frozen study](../../INFORMATION-PROTOCOL.md)
planned 96 responses on eight failed development checkpoints: four draws each
with raw feedback, focused equivalent feedback and focused feedback plus a trace.

The single-use collector was launched from `7fa946f4d89125923a63d08246d9137ee3f114a7`
after 248 offline tests passed (five skipped) and exact-head
[CI succeeded](https://github.com/EmaRimoldi/how-to-pick-a-model/actions/runs/40325852400).
Its first admission returned HTTP 429 without a Retry-After header. The process
stopped, with no receipt, settlement, candidate or verifier outcome. The other
95 planned requests were never admitted. There was no retry or provider fallback.

The [report](REPORT.md) and [analysis](analysis.json) preserve all 96 missing
outcomes and twelve original source candidates. No success rate or mean treatment
effect can be estimated; the primary difference bounds are the uninformative
[-1, 1]. The engineering screen is inconclusive, not a negative scientific result.
No selector is trained, and no information-acquisition benefit is established.

## Accounting and diagnosis

Known new charges: $0. The uncertain admission retains its full $0.0032768
reservation. Added to the prior $0.02211715, cumulative commitment is
**$0.02539395**, including six unresolved calls across the repair campaign,
under the unchanged $0.60 ceiling and this study's $0.34 sublimit.

The subsequent [read-only account check](readonly-limit-check.json) confirmed a
valid paid key with capacity under its declared credit limit and no reported
exhausted budget. It made no generation call. It does not establish availability
at the pinned endpoint, identify the origin of the 429, resolve billing or
authorize repeating the request. The original adapter discarded the error body,
so that detail cannot be recovered retrospectively. Future transport code now
captures only bounded, allowlisted error codes and numeric rate headers, never
server messages, raw metadata or account identifiers. The frozen collector and
original evidence remain unchanged.

No continuation is enabled. Any future segment would require a separately
recorded operational exception and technical review, use only original requests
never admitted, carry this reservation once and keep this cell unknown. Merely
waiting does not establish that the provider recovered.

## Reproduce offline

The [archive manifest](evidence-manifest.json) hashes every raw record and inert
source snapshot. Archive SHA-256:
`f4241d9d1905a29e00b9c89a301570c72695fcf5605adc60a23b120948001e88`.

From the repository root, choose a fresh output path:

```bash
.venv/bin/python scripts/verify_repair_contract_evidence.py \
  --input experiments/python-repair/checkpoint-environment/results/information-interrupted-20261026 \
  --output runs/information-interruption-reverification.json
```

The [independent replay](reverification.json) exactly reproduced the analysis and
Markdown, re-executed all prepared public diagnostic projections, and found no
discrepancy. It checked **zero new candidate evaluations**, because none exist.
This is not validation of model performance. The replay tool was corrected to
handle file-only archives that omit an empty `cells/` directory; a regression
test covers this first-request failure. The archived source retains the original
implementation, and the terminal analysis itself is unchanged.
