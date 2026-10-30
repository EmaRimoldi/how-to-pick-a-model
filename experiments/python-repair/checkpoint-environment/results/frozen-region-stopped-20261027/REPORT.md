# Frozen public-region trace development calibration

Status: **incomplete_frozen_region_development_probe**. Gate: **inconclusive_incomplete_bank**. No selector trained.

Commitment: $0.01836964 / $0.38; cumulative $0.22774335 / $0.60.

| Arm | Observed/planned | Full repairs | False acceptances | Regressions | Missing | Known API USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| focused | 5/16 | 3 | 0 | 1 | 11 | 0.00249160 |
| focused_trace | 6/16 | 4 | 0 | 2 | 10 | 0.00440924 |

Prespecified primary comparison:

```json
{
  "focused_trace_minus_focused": {
    "primary": true,
    "selected_cell_difference_bounds": [
      -0.625,
      0.6875
    ],
    "mean_difference": null,
    "descriptive_bug_bootstrap_95": null
  }
}
```

All eight original-bug sources, 32 selected cells, actual acquisition resources, deployment cost projections and completion extremes are retained in analysis.json.

## Limits

- Eight exposed original buggy artifacts after public-test failure, two generation draws per arm; development only.
- These are not model-generated failed repairs and cannot replace final post-repair-failure policy evaluation.
- Both draws use the same actual frozen acquisition per bug; this tests generation repeatability conditional on that acquisition, not diagnostic stochasticity.
- All eight candidates and all 32 selected cells retained. No historical controls, pooling or filled missing requests.
- Primary focused_trace minus focused, with identical core feedback, solver settings and matched seeds.
- Equal per-call limits are not equal realized spending or equal total-resource budgets.
- Original source artifacts have no API generation charge; historical financial carry is not source-prefix generation cost.
- Frozen diagnostic acquisition is performed once per bug. Counterfactual deployment costs charge it on every planned treatment draw; cached research work is not rebilled.
- Source verification, diagnostic selection and execution, response public verification and evaluator-only research time are reported separately; local seconds are not dollars.
- Prompt projection and full deployment overhead remain outside this calibration and must be accounted for in a later policy runner.
- Incomplete banks have null mean/bootstrap and an inconclusive gate regardless of finite completion bounds; missingness is not assumed random.
- A complete-bank screen pass only permits a separate generated-failure calibration, never selector training.
- Bounded network cooldown may admit only the next never-admitted cell; no retry, resumption, successor, fallback or key rotation.
- Raw SSE bytes are not archived; saved metrics are not byte-level wire replay.
- Trace coverage is bounded, values may be omitted, and independent diagnostic acquisitions may contain stochastic differences.
