# Output-contract development diagnostic

Status: **development_diagnostic_complete**. Gate: **no_contract_meets_engineering_checks**. No selector trained.

Known study charges: $0.00341400; study commitment including reserves: $0.00341400 / $0.09.
Prior repair commitment: $0.01419331; cumulative: $0.01760731 / $0.60.

| Contract | Observed / tasks | Ready source | Ready, unsolved | Full successes | Missing-task bounds | Known API charges | Commitment |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| json_current | 12/12 | 11 | 10 | 1 | [0.083, 0.083] | 0.00118745 | 0.00118745 |
| json_example | 12/12 | 11 | 10 | 1 | [0.083, 0.083] | 0.00117605 | 0.00117605 |
| python_text | 12/12 | 9 | 9 | 0 | [0.000, 0.000] | 0.00105050 | 0.00105050 |

Ready source means a valid file artifact, parseable Python and a top-level declared entrypoint; full success additionally requires both public and evaluator tests. Bounds are worst/best assignments to missing cells, not confidence intervals.

| Task | Current JSON | Example JSON | Python text |
| --- | --- | --- | --- |
| development/bugsinpy-adapted/youtube-dl-003 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-011 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-013 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-020 | tests fail | tests fail | unusable source |
| development/bugsinpy-adapted/youtube-dl-027 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-031 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-032 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-033 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-042 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/youtube-dl-043 | tests fail | tests fail | tests fail |
| development/bugsinpy-adapted/httpie-005 | unusable source | unusable source | unusable source |
| development/bugsinpy-adapted/tornado-009 | pass | pass | unusable source |

Candidate for a separately reviewed future recovery calibration: None.

## Limits

- Already inspected development bugs, one draw per contract: no held-out inference, confidence claim or p-values.
- Text mode changes both prompt wording and provider JSON constraints; effects cannot be attributed to wording alone.
- Container validity is not comparable across encodings. Syntax plus a declared entrypoint also does not prove correctness.
- Missing-cell bounds concern these selected tasks only, not unobserved task populations.
- The engineering gate requires a complete bank. All three contracts remain reported even when none qualifies.
- Equal per-call allowance is not equal actual spending. Local verification and inference timings remain in saved records.
- A candidate passing the practical checks still needs new recovery data and replicated action complementarity before fitting a selector.
