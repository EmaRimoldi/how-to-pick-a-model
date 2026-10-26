# SSE compatibility probe: two receipts, client limit stops the third

**Engineering result, not repair evidence.** All three synthetic requests were
admitted. The first two returned complete, validated SSE responses and usage
receipts. The longest request hit the client's **1 MiB wire limit**, before a
terminal marker or usage receipt, and retains its full reservation. The fixed
three-receipt compatibility gate remains **inconclusive**. No request is retried,
replaced or resumed; this probe has no successor.

| Synthetic payload | Response characters recorded | SSE chunks | Wire bytes | Exchange / response seconds | Receipt |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 function | 306 | 85 | 24,189 | 1.770 | Complete; $0.00008412 |
| 24 functions | 6,675 | 1,719 | 480,439 | 24.252 | Complete; $0.00150864 |
| 64 functions | 14,285 partial | 3,756 | 1,048,653 | 50.538 | Missing; $0.00720896 reserved |

Completed responses ended with `stop` and obeyed the single-file JSON shape.
No code was executed and no function-correctness or repair-success claim is made.
The missing response is neither an observed model failure nor a completed answer.
Only its safe counts/timing/digest were saved, not the partial generated text.

## Identified client defect and its scope

The frozen 1 MiB cap was too small for the SSE envelope overhead at the declared
4096-token output limit. The long request stopped with `stream_protocol_error` /
`wire_limit`, not a recorded connection reset. It was still emitting data when
the cap was reached; this does not establish what would have happened afterward.
The earlier non-streaming resets remain unexplained. There is no randomized
non-streaming comparator or evidence for a production failure-rate improvement.

After terminal audit, an offline regression fixture with 4096 content frames and
realistic per-frame metadata reproduced this limit failure. The same synthetic
fixture completes under an explicit **8 MiB** cap, preserving receipt validation,
reserves and single settlement. The transport now accepts a separately declared
wire cap; the old v1 default and frozen study remain at 1 MiB. A future protocol
must explicitly freeze the larger cap. This offline correction does not fill the
missing live receipt or satisfy the closed probe's gate.

## Accounting and evidence

Known new charges: **$0.00159276**. Uncertain reserve: **$0.00720896**.
Study commitment: **$0.00880172 / $0.03**. Carrying $0.10576463 once gives
**$0.11456635 / $0.60** cumulative commitment, including twelve unresolved
historical/current requests. The first error stopped collection as specified;
no fallback, key rotation, retry or generation lookup occurred.

The [audit](analysis.json) retains all three selected fixtures and verifies exact
requests, unique generation IDs, receipt projections, ledger, uncertainties and
cumulative costs. An [independent frozen-source audit](reverification.json)
reproduces the report exactly from the [hashed archive](evidence-manifest.json).
It makes no API calls and executes no model-generated code. Original SSE wire
bytes were not archived; their digests do not constitute a byte-level replay.
Complete receipts are explicitly reconstructed from SSE. Partial text is absent.

Collection source: `90fa4dcee4d9f5d4c341a4178ec1232b58e176ea`.
Freeze: `0d1e4fab430ef5ea61e837a6eb630ccc85101a51a6eeabb8867e7de82afd2f59`.
Archive SHA-256:
`4f746966054f585017c7c1490cab6ed28ee387b153791a99cca1320ba1e8a47e`.
The [prospective protocol](../../SSE-COMPATIBILITY-PROTOCOL.md) and
[allocation](../../SSE-COMPATIBILITY-AUTHORIZED.json) remain unchanged.

After checking archive and member hashes, extract to a fresh directory and
restore the `source/` Python filenames from `.py.txt` to `.py`. From that source
root, with the repository's pinned Python dependencies available:

```bash
PYTHONPATH=src python scripts/repair_transport_probe.py audit --input ../collection
```

The full acquisition-selector goal remains unfinished. This probe identifies a
client resource-sizing defect and establishes two concrete stream/receipt
exchanges. It establishes neither diagnostic benefit nor a policy advantage.
Any future paid validation requires a distinct reviewed request/source/allocation;
the interrupted fixture and all historical missing cells remain closed.
