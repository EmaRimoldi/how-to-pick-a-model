# Public-trace information development probe

Status: **incomplete_development_information_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Study commitment: $0.01984188 / $0.18; cumulative including historical reserves: $0.10576463 / $0.60.

| Arm | Observed/planned | Full successes | Public false positives | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 5/12 | 4 | 0 | 0 | 7 | 0.00275848 |
| focused_trace | 4/12 | 2 | 0 | 0 | 8 | 0.00266548 |

Primary contrast and all secondary contrasts:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -0.75,
      0.5
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  }
}
```

The screening rule cannot train or certify a policy. Full costs, prefix accounting, local acquisition/verification and all three task records are in analysis.json.

## Limitations

- Three inspected development bugs from two projects; four draws each, no held-out or population inference.
- Initial checkpoints are original upstream buggy versions, not LLM-generated failures; all three are retained. No generated-prefix API cost exists.
- Only primary contrast: focused_trace minus focused on fresh matched requests. No pooling with the closed eight-checkpoint bank.
- Same per-call cap is not equal realized spending or an equal-total-cost policy comparison.
- Prefix charges in the arm tables are counterfactual per deployment, not new billed charges; acquisition cached for research is charged per decision in policy accounting.
- Local executions and measured seconds are separate resources, not converted into API dollars.
- Bootstrap intervals describe only three purposively selected bug clusters and can be unstable; they cannot justify a population claim or selector training.
- A complete-test pass is not a proof of all semantic requirements. Missing outcomes remain unknown; no repeat or imputation.
- The prospective transport policy can retain one missing call and continue independent cells; a second error stops. Every unknown remains reserved and missing; any incomplete bank has a null mean/bootstrap and inconclusive gate.
