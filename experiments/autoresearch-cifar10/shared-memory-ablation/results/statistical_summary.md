# Statistical Summary

This file preserves the clean comparisons used in the public narrative. Trial
IDs refer to `trial_index.md`.

| Comparison | Test | Result | Interpretation |
| --- | --- | --- | --- |
| `T07` vs `T06` | Mann-Whitney U | `U = 63.0`, `p < 0.001`, rank-biserial `r = 0.917` | shared memory strongly improves the exploratory-search distribution |
| `T07` vs `T04` | Mann-Whitney U | `U = 210.0`, `p < 0.001`, rank-biserial `r = 0.647` | shared memory beats the shorter mixed-style no-memory reference |
| `T07` vs `T08` | Mann-Whitney U | `U = 63.0`, `p < 0.001`, rank-biserial `r = 0.917` | shared memory avoids the extreme no-memory outliers |

These are run-level tests inside one probing experiment. They support a signal about
workflow reliability, not a final benchmark claim across tasks or model
families.
