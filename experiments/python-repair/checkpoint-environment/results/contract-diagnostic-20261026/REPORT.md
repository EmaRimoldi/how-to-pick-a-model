# Output-contract development diagnostic

Status: **incomplete_development_diagnostic**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Known study charges: $0.00028113; study commitment including reserves: $0.00179665 / $0.06.
Prior repair commitment: $0.01011411; cumulative: $0.01191076 / $0.60.

| Contract | Observed / tasks | Ready source | Ready, unsolved | Full successes | Missing-task bounds | Known API charges | Commitment |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| json_current | 1/12 | 1 | 1 | 0 | [0.000, 0.917] | 0.00009402 | 0.00160954 |
| json_example | 1/12 | 1 | 1 | 0 | [0.000, 0.917] | 0.0000959 | 0.0000959 |
| python_text | 1/12 | 0 | 0 | 0 | [0.000, 0.917] | 0.00009121 | 0.00009121 |

Ready source means a valid file artifact, parseable Python and a top-level declared entrypoint; full success additionally requires both public and evaluator tests. Bounds are worst/best assignments to missing cells, not confidence intervals.

| Task | Current JSON | Example JSON | Python text |
| --- | --- | --- | --- |
| development/bugsinpy-adapted/youtube-dl-003 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-011 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-013 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-020 | tests fail | tests fail | unusable source |
| development/bugsinpy-adapted/youtube-dl-027 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-031 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-032 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-033 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-042 | missing | missing | missing |
| development/bugsinpy-adapted/youtube-dl-043 | missing | missing | missing |
| development/bugsinpy-adapted/httpie-005 | missing | missing | missing |
| development/bugsinpy-adapted/tornado-009 | missing | missing | missing |

Candidate for a separately reviewed future recovery calibration: None.

## Limits

- Already inspected development bugs, one draw per contract: no held-out inference, confidence claim or p-values.
- Text mode changes both prompt wording and provider JSON constraints; effects cannot be attributed to wording alone.
- Container validity is not comparable across encodings. Syntax plus a declared entrypoint also does not prove correctness.
- Missing-cell bounds concern these selected tasks only, not unobserved task populations.
- The engineering gate requires a complete bank. All three contracts remain reported even when none qualifies.
- Equal per-call allowance is not equal actual spending. Local verification and inference timings remain in saved records.
- A candidate passing the practical checks still needs new recovery data and replicated action complementarity before fitting a selector.
