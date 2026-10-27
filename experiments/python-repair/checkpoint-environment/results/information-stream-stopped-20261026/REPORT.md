# Public-trace information development probe

Status: **incomplete_development_information_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Study commitment: $0.00799576 / $0.47; cumulative including historical reserves: $0.12585127 / $0.60.

| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 1/32 | 0 | 1 | 0 | 31 | 0.0007868 |
| focused_trace | 0/32 | 0 | 0 | 0 | 32 | 0 |

Primary contrast and all secondary contrasts:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -0.96875,
      1.0
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
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
- A first transport error closes the study without retry or resumption; historical uncertainties remain reserved. Incomplete banks have null mean/bootstrap and an inconclusive gate.
