# Public-trace information development probe

Status: **incomplete_development_information_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Study commitment: $0.0032768 / $0.34; cumulative including historical reserves: $0.02539395 / $0.60.

| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0/32 | 0 | 0 | 0 | 32 | 0 |
| focused | 0/32 | 0 | 0 | 0 | 32 | 0 |
| focused_trace | 0/32 | 0 | 0 | 0 | 32 | 0 |

Primary contrast and all secondary contrasts:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -1.0,
      1.0
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  },
  "focused_minus_raw": {
    "primary": false,
    "selected_cell_difference_bounds": [
      -1.0,
      1.0
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  },
  "focused_trace_minus_raw": {
    "primary": false,
    "selected_cell_difference_bounds": [
      -1.0,
      1.0
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  }
}
```

The screening rule cannot train or certify a policy. Full costs, prefix accounting, local acquisition/verification and all twelve task records are in analysis.json.

## Limitations

- Eight eligible inspected bugs, four draws at one saved checkpoint each; no held-out or independent-replicate inference.
- The other four public passes are retained without intervention, including the known false-positive/specification-ambiguity cases.
- Primary contrast: focused_trace minus focused. raw contrasts are secondary and cannot replace a null primary.
- Same per-call cap is not equal realized spending or an equal-total-cost policy comparison.
- Prefix charges in the arm tables are counterfactual per deployment, not new billed charges; acquisition cached for research is charged per decision in policy accounting.
- Local executions and measured seconds are separate resources, not converted into API dollars.
- Bootstrap intervals describe eight selected bug clusters; repeated draws and a screening gate do not establish action complementarity or authorize selector training.
- A complete-test pass is not a proof of all semantic requirements. Missing outcomes remain unknown; no repeat or imputation.
