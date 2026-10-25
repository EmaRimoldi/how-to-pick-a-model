# Context-value prospective diagnostic

Status: `complete`. 60 initial attempts; 4 visible failures; 4 complete matched checkpoints across 3 tasks.

API collection cost: $0.023022; unresolved conservative reservations: $0.000000. Forecast API cost included: $0.000540.

| Model.condition | Task-macro full-suite success | Mean incremental API USD |
| --- | --- | --- |
| small.fresh | 41.7% | 0.00004806 |
| small.artifact | 33.3% | 0.00005221 |
| small.feedback | 33.3% | 0.00006569 |
| small.artifact_feedback | 33.3% | 0.00006244 |
| large.fresh | 66.7% | 0.00085500 |
| large.artifact | 41.7% | 0.00053588 |
| large.feedback | 66.7% | 0.00056567 |
| large.artifact_feedback | 100.0% | 0.00059187 |

| Paired contrast | Task-macro success difference | Task-cluster bootstrap 95% interval |
| --- | --- | --- |
| small.artifact_minus_fresh | -8.3% | insufficient task clusters |
| small.feedback_minus_fresh | -8.3% | insufficient task clusters |
| small.both_minus_fresh | -8.3% | insufficient task clusters |
| small.interaction | +8.3% | insufficient task clusters |
| large.artifact_minus_fresh | -25.0% | insufficient task clusters |
| large.feedback_minus_fresh | +0.0% | insufficient task clusters |
| large.both_minus_fresh | +33.3% | insufficient task clusters |
| large.interaction | +58.3% | insufficient task clusters |

| Prospective forecast | Brier score (lower is better) |
| --- | --- |
| task_only | 0.22654 |
| state | 0.19663 |
| constant_0.5 | 0.25000 |

Invalid forecasts retained with 0.5 fallback: {'task_only': 0, 'state': 0}.
Incomplete matched checkpoints excluded from paired effects: [].

Repeated draws are averaged within checkpoints, then checkpoints within tasks; tasks are equally weighted. Intervals resample tasks (4000 draws, seed 20261023), are exploratory and are not adjusted for multiple contrasts. They cover variation in this selected task subset, not provider drift or benchmark contamination.

Forecasts were saved before the branch outcomes. These are zero-shot forecasts, not a trained controller. A forecast deployment must pay its own forecasting cost; fixed-arm costs in the table exclude forecasting and the already-sunk prefix. The receipt bundle accounts for every paid call.

Artifact/feedback inclusion also changes prompt length. Feedback can quote code. No length-matched irrelevant-context control or equal-dollar adaptive-policy comparison is present. Public feedback may miss failures detected by the broader evaluation suite. No novelty, policy-superiority or general-gain claim.

## Forecast overhead

Mean task_only forecast API cost per failed checkpoint (task macro): $0.00005380.
Mean state forecast API cost per failed checkpoint (task macro): $0.00008010.

A better forecast is economically useful only when the resulting decisions recover its overhead. This analysis does not equate lower Brier score with net cost savings.
