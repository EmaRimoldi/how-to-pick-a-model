# Offline qualification of a revised public diagnostic

**Both single and paired diagnostics are available on all eight exposed failing
checkpoints; no model was called.** All twelve original candidates are retained,
including four public-pass sources that correctly trigger no acquisition.

This is engineering evidence for the [proposed intervention](../../CONTRASTIVE-DIAGNOSTIC-DESIGN.md),
not evidence that contrastive traces repair more bugs or support a selector.

The qualification executed 48 sandboxed cases (two for each single acquisition,
four for each pair) plus one sandbox-boundary preflight. Traced and ordinary
observations agree with recorded public feedback. Across separate acquisitions,
the failing trace is identical. Both prompts preserve the same existing code,
public tests and feedback. The lossless representation roundtrips every retained
event and preserves omissions and truncation.

| Bug | Failing case | Selected passing case | Raw / represented trace bytes | Single / paired prompt bytes |
| --- | --- | --- | ---: | ---: |
| youtube-dl-003 | stray-before-quote | named | 2575 / 2575 | 6156 / 8325 |
| youtube-dl-013 | rtmp-no-base | http-no-base | 1692 / 1692 | 4767 / 6131 |
| youtube-dl-020 | boolean-before | wrong | 2829 / 2298 | 7070 / 9393 |
| youtube-dl-031 | minutes | units | 2076 / 2076 | 5559 / 8200 |
| youtube-dl-033 | fraction-z | zone | 4929 / 3435 | 6860 / 10315 |
| youtube-dl-042 | existing | decimal | 1775 / 1775 | 4414 / 6106 |
| youtube-dl-043 | deep | two | 1384 / 1384 | 3749 / 5059 |
| httpie-005 | long-escape | json | 10536 / 4424 | 8862 / 13312 |

Bytes are canonical UTF-8 JSON, not provider tokens or dollars. The represented
trace is shorter on three sources and raw on five; the paired prompt is larger
than the single prompt on all eight. A nearest public input need not isolate the
bug: for example, the HTML pair selects a no-match passing test. We preserve that
choice rather than selecting a favorable pair by hand.

An earlier offline representation/ranking prototype, before any model call,
used similarity over serialized JSON and unconditionally delta-encoded traces.
It sometimes preferred empty/root examples and expanded five traces. We replaced
serialization similarity with normalized input-value edit distance and retained
raw encoding when shorter. Earlier records/sources remain locally preserved;
this is development iteration, not a preregistered effectiveness comparison.

## Saved records and reproduction

[qualification.json](qualification.json) records every source, source hashes,
observed timing, selection and sizes. [records.zip](records.zip) contains public
inputs, both diagnostics/prompts and inert source copies; [manifest.json](manifest.json)
pins every member. No evaluator expectations, provider credentials or model
receipts are included. The upstream source archive is independently hash-checked
before preparation. Original model-study data are not changed.

```bash
uv run python scripts/prepare_contrastive_diagnostics.py \
  --input experiments/python-repair/checkpoint-environment/results/information-independent-20261026 \
  --output runs/fresh-contrastive-qualification
```

Requires the existing macOS sandbox backend. Use a fresh directory. Measured wall
times may vary; public observations, selections and request projections are
deterministic for these cases. Unit tests cover missing passing cases, observation
mismatch, information boundaries, recursive trace reconstruction, and archive
projection replay. A separate real-sandbox test exercises acquisition end to end.

No collector is active. This preparation does not authorize paid collection,
establish useful action headroom, or complete the held-out policy objective.
