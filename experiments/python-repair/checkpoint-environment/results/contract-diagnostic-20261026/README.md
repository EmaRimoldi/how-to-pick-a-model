# Gemma 4B output-contract diagnostic: interrupted, inconclusive

The authorized $0.06 Parasail study stopped with HTTP 429 on its fourth admitted
request, despite 60-second spacing. No request was retried or resumed. The freeze
was `706767db4546707bfcd2799aadd0b25a5e726d88df7febc3c4124c34cc0e74e2`, source
`709de3500013c6ce51cb6b0152e09cdd86981946`. The full authorization, packet and prior
financial report are embedded in the archived collection manifest.

Three responses cover all three formats on only `youtube-dl-020`; none passes
both test suites. The two JSON responses produce parseable files with the declared
entrypoint but fail tests. The text response does not produce usable Python under
the prespecified strict decoder. These three observations cannot rank the formats.
All twelve selected bugs remain in [the report](REPORT.md): 33/36 outcomes are
missing (one uncertain admission and 32 never sent), rather than model failures.
The incomplete-bank gate is inconclusive and no selector was trained.

| Accounting | USD |
| --- | ---: |
| Known new generation charges | 0.00028113 |
| Retained uncertain-call reserve | 0.00151552 |
| New study commitment / cap | 0.00179665 / 0.06 |
| Closed recovery pilot commitment | 0.01011411 |
| Cumulative commitment / ceiling | 0.01191076 / 0.60 |

The error is an operational limitation, not evidence of solver inability or an
exhausted monetary cap. No account identifiers or credentials are included.
All archived requests, settlements and raw/normalized receipts pass the audit.
The portable archive reproduced the entire JSON analysis and Markdown report
from an isolated extraction. Six saved verification records (four unique
artifact/test-suite inputs) were re-executed in the macOS sandbox with **zero
discrepancies and zero API calls**; see [reverification.json](reverification.json).

## Reproduce without model calls

Verify the ZIP SHA-256 and every member against [evidence-manifest.json](evidence-manifest.json),
then extract [evidence.zip](evidence.zip) into a fresh directory. All model output
is inert JSON; frozen collector sources are `.py.txt` records. Use the repository's
installed environment and an absolute extracted path:

```bash
uv run python scripts/collect_repair_contract_probe.py audit --input /absolute/extraction/collection
uv run python scripts/report_repair_contract_probe.py --input /absolute/extraction/collection --output runs/contract-reproduced
```

Both `analysis.json` and `REPORT.md` must match exactly. The reporter does not
contact providers or execute saved code. Sandbox reverification is a separate
local action; never execute model artifacts directly.

The [original protocol](../../CONTRACT-PROBE-PROTOCOL.md) remains unchanged.
After the user instructed “Non farti problemi di denaro. Continua.”, a separately
specified [DeepInfra follow-up](../../CONTRACT-DEEPINFRA-PROTOCOL.md) was prepared.
It does not complete or pool this bank and does not establish a provider effect.
