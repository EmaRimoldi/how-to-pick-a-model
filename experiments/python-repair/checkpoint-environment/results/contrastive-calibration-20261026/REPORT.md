# Public contrastive-trace development calibration

Status: **complete_contrastive_development_probe**. Gate: **no_completion_meets_development_screen**. No selector trained.

Commitment: $0.04144616 / $0.40; cumulative $0.20640271 / $0.60.

| Arm | Observed/planned | Full repairs | False acceptances | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 24/24 | 6 | 2 | 5 | 0 | 0.01192604 |
| single_trace | 24/24 | 9 | 3 | 2 | 0 | 0.01475424 |
| paired_trace | 24/24 | 9 | 2 | 3 | 0 | 0.01476588 |

Primary and fixed secondary comparisons:

```json
{
  "paired_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      0.125,
      0.125
    ],
    "mean_difference": 0.125,
    "descriptive_bug_bootstrap_95": [
      0.041666666666666664,
      0.25
    ]
  },
  "paired_trace_minus_single_trace": {
    "primary": false,
    "selected_cell_difference_bounds": [
      0.0,
      0.0
    ],
    "mean_difference": 0.0,
    "descriptive_bug_bootstrap_95": [
      -0.16666666666666666,
      0.20833333333333331
    ]
  },
  "single_trace_minus_focused": {
    "primary": false,
    "selected_cell_difference_bounds": [
      0.125,
      0.125
    ],
    "mean_difference": 0.125,
    "descriptive_bug_bootstrap_95": [
      -0.041666666666666664,
      0.29166666666666663
    ]
  }
}
```

All twelve sources, unobserved cells, cost components and completion extremes are retained in analysis.json.

## Limits

- Eight exposed checkpoints, seven youtube-dl and one httpie, three draws per arm; development only.
- All twelve original sources retained; four public passes do not trigger acquisition, including evaluator failures.
- Primary paired_trace minus focused; favorable single-trace contrasts cannot replace it.
- New concurrent requests only; no pooling, reused historical controls or filled missing requests.
- Three-draw finite screen is newly prospective; no historical four-draw gate is changed.
- Equal per-call limits are not equal realized spending or an equal-total-budget policy test.
- Counterfactual prefix and diagnostic resources are charged for every planned deployment, not rebilled research API charges.
- Selection/preparation time is included in diagnostic_seconds; prompt projection and full deployment overhead still need policy accounting.
- Public response verification and private evaluator research time are separate; local time is not converted to dollars.
- Incomplete banks retain null mean/bootstrap and finite selected-cell bounds; no random-missingness assumption.
- A screen pass permits only a separately reviewed independent calibration, never selector training.
- The network-error rule permits only never-admitted scheduled cells after bounded cooldown; no retry/resumption or key rotation.
- Raw SSE bytes are not archived; saved metrics are not byte-level wire replay.
- Input similarity need not expose a useful semantic contrast; omitted trace values remain omitted.
