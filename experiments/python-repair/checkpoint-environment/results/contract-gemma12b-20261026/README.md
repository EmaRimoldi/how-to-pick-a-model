# Complete Gemma 3 12B capability calibration

All **36/36** planned calls completed; every response has a verified outcome.
**No format passed the unchanged calibration gate; no selector was trained.**

| Format | Usable source / 12 | Ready but unsolved | Full successes / 12 |
| --- | ---: | ---: | ---: |
| Current JSON | 11 | 10 | 1 |
| JSON with example | 11 | 10 | 1 |
| Plain Python | 9 | 9 | 0 |

Both full successes concern **the same Tornado/9 bug**. They are not two distinct
solved problems. The fixed gate required at least three distinct solved bugs per
format, ten usable artifacts and two usable unsuccessful artifacts. Neither JSON
format meets the solved-bug requirement; the text format also lacks enough usable
artifacts. No format is selected by the rule.

The preceding [4B diagnostic](../contract-deepinfra-20261026/README.md) yielded
4/12, 5/12 and 7/12 usable artifacts and 0/12, 1/12 and 0/12 full successes.
The observed 12B validity counts are higher, while complete repair remains rare.
These separate one-draw development studies do not establish a population-level
improvement, causal parameter-count effect, emergence or scaling law. Seed/order,
pacing and pricing differ, and model pretraining exposure also differs. The
same task/contract messages were checked byte-for-byte before collection.

## Structural follow-up and limits

A separately labeled **post hoc** [AST diagnostic](artifact-diagnostic.json)
finds 8/31 syntax-valid outputs structurally unchanged from supplied source.
The other 23 have different ASTs, but a structural edit does not establish useful
behavioral change. This check does not filter any observation, alter the gate or
prove semantic equivalence. It reproduces exactly from archived inputs.

This initial-repair diagnostic collects no continue/restart branches and cannot
establish action complementarity. All twelve adapted BugsInPy tasks are already
inspected development data, including ten youtube-dl tasks. One draw per contract
and bug supports no held-out inference, confidence claim or p-value. The failed
calibration remains evidence even if a later stronger model/setup succeeds.
A separate capability control or setup diagnostic is needed before fitting a
repair selector; do not lower the gate to make this bank qualify.

## Accounting and evidence

Known study charges: **$0.00341400 / $0.09**, with no missing or uncertain new
request. Carry **$0.01419331** from the closed studies exactly once, including
all five historical unresolved calls. Cumulative commitment is
**$0.01760731 / $0.60**. API charges and saved local-verifier timings are separate.

- [Prospective protocol](../../CONTRACT-12B-PROTOCOL.md) and
  [authorization](../../CONTRACT-12B-AUTHORIZED.json).
- Source: `c21ba5e180dd4ecc560b5169a58aba3702daff00`.
- Packet: `22587df7d4a5d2602a7da7932563feb4174225279edbe84ed9fef82a7cfbe2ce`.
- Freeze: `cfbc93062fc98fe593fa860181c8b6a638828af31480db6b7f27948d79969b07`.
- [Full selected-cell report](REPORT.md), [analysis](analysis.json),
  [portable evidence](evidence.zip), [member hashes](evidence-manifest.json),
  [independent sandbox verification](reverification.json).

Exact requests, raw receipts, ledger, tasks, authorization, prior cumulative
report and inert frozen sources are preserved. No previous study is resumed,
repeated or pooled into this one. There is no retry or implicit fallback.

## Reproduce

From the repository root, in the installed project environment:

```bash
uv run python scripts/verify_repair_contract_evidence.py \
  --input experiments/python-repair/checkpoint-environment/results/contract-gemma12b-20261026 \
  --output runs/gemma12b-independent-verification.json
```

Use a new output path. The command verifies archive/member hashes, extracts into
a temporary directory, reproduces full JSON/Markdown and re-executes saved
artifacts in the macOS sandbox with **zero API calls**. All **72 evaluation
records / 60 unique artifact-suite inputs** reproduced with **zero discrepancies**;
only runtime timings are excluded from equality. No unrestricted fallback exists.
Portable report-only reproduction uses `scripts/report_repair_contract_probe.py`
on the hash-verified extracted `collection/` directory. Frozen source is `.txt`,
and model artifacts remain JSON.

After hash verification/extraction, the post hoc check is separately reproducible:

```bash
uv run python experiments/python-repair/checkpoint-environment/results/contract-gemma12b-20261026/diagnose.py \
  --input <extracted>/collection --output runs/gemma12b-structural-diagnostic.json
```
