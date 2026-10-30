# Public-trace information development probe

Status: **complete_development_information_probe**. Gate: **no_completion_meets_development_screen**. No selector trained.

Study commitment: $0.03910528 / $0.47; cumulative including historical reserves: $0.16495655 / $0.60.

| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 32/32 | 12 | 2 | 6 | 0 | 0.01795952 |
| focused_trace | 32/32 | 8 | 2 | 6 | 0 | 0.02114576 |

Primary contrast and all secondary contrasts:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -0.125,
      -0.125
    ],
    "mean_difference": -0.125,
    "descriptive_bug_bootstrap_95": [
      -0.3125,
      0.03125
    ]
  }
}
```

The screening rule cannot train or certify a policy. Full costs, prefix accounting, local acquisition/verification and all twelve task records are in analysis.json.

## Limitations

- Eight already exposed failed checkpoints (seven youtube-dl, one httpie), four fresh draws per arm; development only, no held-out inference.
- The other four public passes are retained without intervention, including the known false-positive/specification-ambiguity cases.
- Only primary contrast: focused_trace minus focused in this separate streaming bank; no pooling, historical concurrent controls or filling of old missing cells.
- Same per-call cap is not equal realized spending or an equal-total-cost policy comparison.
- Prefix charges in the arm tables are counterfactual per deployment, not new billed charges; acquisition cached for research is charged per decision in policy accounting.
- Local executions and measured seconds are separate resources, not converted into API dollars.
- Bootstrap intervals describe eight selected bug clusters; repeated draws and a screening gate do not establish action complementarity or authorize selector training.
- A complete-test pass is not a proof of all semantic requirements. Missing outcomes remain unknown; no repeat or imputation.
- Previous outcomes were inspected before this protocol; the same development sources and previously specified screen are retained, with a new seed and explicit 8 MiB streaming envelope. No causal transport or scaling-law inference.
- Complete SSE receipts are reconstructed and audited with saved metrics; raw wire bytes are not archived, so their byte-level replay is unavailable.
- Prospective independent-cell rule retains at most seven no-receipt network errors; the eighth total or third consecutive error stops, as do all other errors. Missing cells stay unknown and reserved. No retries or resumption.
- The new development screen passes only if every binary completion of missing outcomes satisfies all efficacy thresholds. Upper-bound failure rejects only this finite screen, not a population benefit. Incomplete mean/bootstrap stay null; historical complete-bank gates are unchanged.
