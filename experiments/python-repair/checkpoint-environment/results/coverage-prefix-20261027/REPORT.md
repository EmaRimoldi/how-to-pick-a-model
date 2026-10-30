# Natural-failure difficulty calibration

Status: **complete_initial_calibration**. Gate: **insufficient_failure_coverage_headroom**.

Full repairs: 4/6; missing: 0. Natural recovery checkpoints: 2; with multiple public failures: 2.

Cumulative commitment: $0.20937371 / $0.60, including historical reserves.

| Task | Observed | Full repair | Public failures | Public false acceptance | Recovery checkpoint |
| --- | --- | --- | --- | --- | --- |
| development/bugsinpy-adapted/scrapy-002 | True | True | 0 | False | False |
| development/bugsinpy-adapted/scrapy-036 | True | True | 0 | False | False |
| development/bugsinpy-adapted/luigi-010 | True | True | 0 | False | False |
| development/bugsinpy-adapted/tornado-005 | True | False | 6 | False | True |
| development/bugsinpy-adapted/thefuck-022 | True | False | 3 | False | True |
| development/bugsinpy-adapted/thefuck-029 | True | True | 0 | False | False |

Six purposively selected development bugs, one initial draw; no held-out claim.
Eligibility uses decoded artifacts and public failures only, never private correctness.
Missing and malformed outputs remain in the six-task denominator.
Passing the difficulty gate permits only the separate prespecified recovery stage.
The selector and equal-total-resource policy benefit remain unestablished.

No diagnostic-benefit claim and no selector training.
