# Repair interface development control

Status: **incomplete_development_interface_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Study commitment: $0.01068272 / $0.43; cumulative including prior reserves: $0.05126739 / $0.60.

| Condition | Observed/planned | Full repairs | Copies | Entrypoint-only edits | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| original | 11/32 | 0 | 5 | 3 | 0 | 21 | 0.00184168 |
| claim_removed | 11/32 | 0 | 6 | 2 | 0 | 21 | 0.00181952 |
| helpers_explicit | 11/32 | 0 | 4 | 3 | 0 | 21 | 0.00188448 |
| both | 11/32 | 0 | 4 | 2 | 0 | 21 | 0.00186024 |

Primary and secondary contrasts:

```json
{
  "both_minus_original": {
    "primary": true,
    "weights": {
      "both": 1,
      "original": -1
    },
    "selected_cell_difference_bounds": [
      -0.65625,
      0.65625
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  },
  "claim_removal_main_effect": {
    "primary": false,
    "weights": {
      "claim_removed": 0.5,
      "both": 0.5,
      "original": -0.5,
      "helpers_explicit": -0.5
    },
    "selected_cell_difference_bounds": [
      -0.65625,
      0.65625
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  },
  "explicit_helpers_main_effect": {
    "primary": false,
    "weights": {
      "helpers_explicit": 0.5,
      "both": 0.5,
      "original": -0.5,
      "claim_removed": -0.5
    },
    "selected_cell_difference_bounds": [
      -0.65625,
      0.65625
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  },
  "interaction": {
    "primary": false,
    "weights": {
      "both": 1,
      "original": 1,
      "claim_removed": -1,
      "helpers_explicit": -1
    },
    "selected_cell_difference_bounds": [
      -1.3125,
      1.3125
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  }
}
```

## Limitations

- Eight exposed failure checkpoints with four draws each; twelve source candidates retained. No untouched evaluation.
- Primary: both cues minus original. Factorial main effects and interaction are secondary, not substitutes for the primary screen.
- Incomplete banks retain finite selected-cell missingness bounds; no complete-bank mean, bootstrap or screen is computed.
- Complete-bank paired bug bootstrap intervals are descriptive; eight clusters cannot support broad population inference.
- Syntax categories do not establish semantic equivalence or identify psychological anchoring or general model intelligence.
- Fewer copies or more changed code is not the objective; full public-plus-evaluator repair is required, with false acceptance and regressions retained.
- Equal call caps do not mean equal actual spending or a policy-level budget advantage. Prefix costs are counterfactual, not newly billed.
- Local verification and provider latency are separate resources. Operational request pacing is not a policy decision cost.
- No trace is acquired in this control and no acquisition policy or repair selector is trained. A passed screen only permits independent calibration.
