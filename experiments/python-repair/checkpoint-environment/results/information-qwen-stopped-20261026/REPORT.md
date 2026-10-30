# Public-trace information development probe

Status: **incomplete_development_information_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Study commitment: $0.01649536 / $0.47; cumulative including historical reserves: $0.08592275 / $0.60.

| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 9/32 | 2 | 2 | 5 | 23 | 0.00458044 |
| focused_trace | 9/32 | 3 | 0 | 2 | 23 | 0.00470596 |

Primary contrast and all secondary contrasts:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -0.6875,
      0.75
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
- Primary and only arm contrast: focused_trace minus focused; fresh concurrent controls, no historical-control substitution.
- Same per-call cap is not equal realized spending or an equal-total-cost policy comparison.
- Prefix charges in the arm tables are counterfactual per deployment, not new billed charges; acquisition cached for research is charged per decision in policy accounting.
- Local executions and measured seconds are separate resources, not converted into API dollars.
- Bootstrap intervals describe eight selected bug clusters; repeated draws and a screening gate do not establish action complementarity or authorize selector training.
- A complete-test pass is not a proof of all semantic requirements. Missing outcomes remain unknown; no repeat or imputation.
- Solver compatibility qualified this development model. This is not a causal comparison with Gemma or evidence of a scaling law.
