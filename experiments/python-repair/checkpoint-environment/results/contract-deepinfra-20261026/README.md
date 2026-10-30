# Complete Gemma 3 4B output-contract calibration

All **36/36** planned calls completed on the pinned DeepInfra bf16 route. The
prospectively fixed engineering gate failed for every format. **No format was
selected and no continue/restart selector was trained.**

| Format | Usable Python with required entrypoint | Fully solved bugs |
| --- | ---: | ---: |
| Current JSON | 4/12 | 0/12 |
| JSON with example | 5/12 | 1/12 |
| Plain Python | 7/12 | 0/12 |

The sole full success is Tornado/9 under JSON with example. The gate required at
least ten usable artifacts, three distinct solved bugs and two usable unsolved
artifacts. Plain Python produces more usable files in this small draw, but that
does not establish a better repair method. The text arm changes both wording and
serving mode. Syntax/entrypoint checks alone do not prove correctness.

This is a complete development diagnostic on twelve already inspected adapted
BugsInPy tasks, ten from youtube-dl. There is one draw per bug and format: no
population inference, p-values, held-out evaluation or provider-effect claim.
The prior incomplete Parasail bank remains separate. The current data cannot
establish action complementarity, because no recovery branches were collected.
Changing output format alone did not make this setup pass its practical gate.
Do not relax that gate or fit a selector to these results. A separately frozen
capability/calibration study is needed before collecting recovery branches.

## Accounting and provenance

Known new charges: **$0.00228255**, with no new missing response or unresolved
reserve, against a $0.08 study cap. Carry **$0.01191076** from the two closed
banks exactly once, including five unresolved historical calls. Total
commitment is **$0.01419331 / $0.60**. Local verification time is retained in
records and is separate from API charges.

- Study: `repair-contract-deepinfra-v1`.
- [Frozen protocol](../../CONTRACT-DEEPINFRA-PROTOCOL.md) and
  [authorized configuration](../../CONTRACT-DEEPINFRA-AUTHORIZED.json).
- Source commit: `9648421c273431c7bfe6617fec69832d55ad656a`.
- Packet: `e38f55dd5013ec9bf25e10a1c5de4390bbb7da5ae246a8145ce7c260933f2640`.
- Freeze: `de439ad32fbf553a425d6e6a54c1096e590b19f1685da8db3554c94fb25b5a91`.
- [Every selected cell and prespecified comparison](REPORT.md),
  [machine-readable analysis](analysis.json), [archive](evidence.zip),
  [hash manifest](evidence-manifest.json), [independent verification](reverification.json).

## Reproduction

From the repository root, with the normal project environment installed:

```bash
uv run python experiments/python-repair/checkpoint-environment/results/contract-deepinfra-20261026/reproduce.py \
  --input experiments/python-repair/checkpoint-environment/results/contract-deepinfra-20261026 \
  --output runs/deepinfra-independent-verification.json
```

The output must not exist. This verifies every archive member hash, extracts
into a fresh temporary directory, reproduces the complete JSON and Markdown,
then re-executes saved artifacts through the existing macOS sandbox. It makes
**zero API calls** and never executes extracted source snapshots directly.
The verification requires macOS `sandbox-exec`; there is no unrestricted fallback.
All **42 evaluation records / 40 unique artifact-suite inputs** reproduced with
**zero discrepancies**. Only runtime timing fields are excluded from comparison.
Analysis without candidate execution is portable: extract the hash-verified
archive and run `scripts/report_repair_contract_probe.py --input <dir>/collection
--output <new-report>`. Frozen collector sources are inert `.txt`; model artifacts
remain JSON. Neither closed study may be resumed or repeated.
