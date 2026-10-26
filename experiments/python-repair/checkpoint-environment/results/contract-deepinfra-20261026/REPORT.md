# Output-contract development diagnostic

Status: **development_diagnostic_complete**. Gate: **no_contract_meets_engineering_checks**. No selector trained.

Known study charges: $0.00228255; study commitment including reserves: $0.00228255 / $0.08.
Prior repair commitment: $0.01191076; cumulative: $0.01419331 / $0.60.

| Contract | Observed / tasks | Ready source | Ready, unsolved | Full successes | Missing-task bounds | Known API charges | Commitment |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| json_current | 12/12 | 4 | 4 | 0 | [0.000, 0.000] | 0.00066375 | 0.00066375 |
| json_example | 12/12 | 5 | 4 | 1 | [0.083, 0.083] | 0.00078195 | 0.00078195 |
| python_text | 12/12 | 7 | 7 | 0 | [0.000, 0.000] | 0.00083685 | 0.00083685 |

Ready source means a valid file artifact, parseable Python and a top-level declared entrypoint; full success additionally requires both public and evaluator tests. Bounds are worst/best assignments to missing cells, not confidence intervals.

| Task | Current JSON | Example JSON | Python text |
| --- | --- | --- | --- |
| development/bugsinpy-adapted/youtube-dl-003 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-011 | unusable source | unusable source | unusable source |
| development/bugsinpy-adapted/youtube-dl-013 | unusable source | unusable source | tests fail |
| development/bugsinpy-adapted/youtube-dl-020 | tests fail | tests fail | unusable source |
| development/bugsinpy-adapted/youtube-dl-027 | unusable source | unusable source | tests fail |
| development/bugsinpy-adapted/youtube-dl-031 | unusable source | unusable source | tests fail |
| development/bugsinpy-adapted/youtube-dl-032 | unusable source | unusable source | unusable source |
| development/bugsinpy-adapted/youtube-dl-033 | unusable source | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-042 | unusable source | unusable source | unusable source |
| development/bugsinpy-adapted/youtube-dl-043 | tests fail | unusable source | tests fail |
| development/bugsinpy-adapted/httpie-005 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/tornado-009 | unusable source | pass | unusable source |

Candidate for a separately reviewed future recovery calibration: None.

## Limits

- Already inspected development bugs, one draw per contract: no held-out inference, confidence claim or p-values.
- Text mode changes both prompt wording and provider JSON constraints; effects cannot be attributed to wording alone.
- Container validity is not comparable across encodings. Syntax plus a declared entrypoint also does not prove correctness.
- Missing-cell bounds concern these selected tasks only, not unobserved task populations.
- The engineering gate requires a complete bank. All three contracts remain reported even when none qualifies.
- Equal per-call allowance is not equal actual spending. Local verification and inference timings remain in saved records.
- A candidate passing the practical checks still needs new recovery data and replicated action complementarity before fitting a selector.
