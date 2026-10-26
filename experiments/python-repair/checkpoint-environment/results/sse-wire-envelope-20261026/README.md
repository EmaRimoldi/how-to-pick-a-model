# Explicit larger SSE envelope: engineering criterion met

The one new integer-enumeration request completed with a validated final receipt
beyond the former wire limit. All four prospectively declared conditions hold:

| Condition | Recorded evidence |
| --- | --- |
| Complete stable-identity response and final usage receipt | 1 admitted, 1 received, 0 new uncertainties |
| More than 1,048,576 wire bytes | 1,112,924 bytes across 4,030 parsed chunks |
| Full output-token ceiling reached | 4,096 reported completion tokens |
| Output-budget termination | `finish_reason: length` |

The explicit client wire cap was 8,388,608 bytes. Elapsed response time was
56.756 seconds; 4,106 content characters were assembled. The requested enumeration
was intentionally larger than the output budget. Its truncated text is a billed
observation, not a correctness score or evidence of poor repair performance.
No generated code was executed and no benchmark task was used.

This verifies the larger envelope on **one concrete exchange**. It does not
estimate service reliability, prove that streaming caused fewer resets, establish
trace benefit or validate a selector. The earlier three-fixture probe remains
inconclusive: its long clamp request was not repeated or filled, and its charge
remains reserved. All old scientific banks remain separate and closed.

## Costs and reproduction

Known new charge and study commitment: **$0.00328916 / $0.01**. There is no new
uncertainty. Carrying $0.11456635 once gives **$0.11785551 / $0.60** cumulative
commitment, still including all twelve older unresolved requests. No fallback,
retry, key rotation or generation lookup occurred.

The [audit](analysis.json) preserves the exact request, receipt, usage, wire
metrics, ledger and cumulative accounting. An [independent frozen-source audit](reverification.json)
reproduces it exactly from the [hashed evidence archive](evidence-manifest.json),
without API calls or executing candidate code. Complete responses are reconstructed
from SSE; raw wire bytes are not archived, so the wire digest is not a claim of
byte-level replay. The prior report and source/protocol/config identities are
bound in the freeze.

Collection source: `ca0c74eb1c8c9350288c2025c8fc52a58ccfc507`.
Freeze: `63585cdadee5f43bb86c8a1a9f2abec50776a3b7964eb4680a24ff910d40339c`.
Archive SHA-256:
`2baf7a00a7fc76d7e49c7027a5b2d9716fe9cf3b642b56fe6bf73d285ca7e5e1`.
Read the [unchanged prospective protocol](../../SSE-WIRE-ENVELOPE-PROTOCOL.md)
and [allocation](../../SSE-WIRE-ENVELOPE-AUTHORIZED.json).

After verifying archive/member hashes, extract to a fresh directory and restore
`source/` Python filenames from `.py.txt` to `.py`. With the pinned dependencies
available, run from that source root:

```bash
PYTHONPATH=src python scripts/repair_transport_probe.py audit --input ../collection
```

The engineering criterion permits preparation of a separately reviewed scientific
calibration. It does not authorize old requests or selector training. The next
scientific requirement remains a complete matched comparison of trace versus
same-information feedback; total-resource fixed policies and untouched-bug
selector evaluation are subsequent requirements of the active goal.
