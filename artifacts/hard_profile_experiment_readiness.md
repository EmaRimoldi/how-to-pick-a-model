# Hard Profile Experiment Readiness

| run | steps | total sec/step incl. baseline | post-baseline sec/step | USD/step | input tok/step | output tok/step | proposal fail | verifier fail |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `local_1step` | 1 | 143.1 | 78.6 |  |  |  | 0.000 | 0.000 |
| `local_2step` | 2 | 111.0 | 78.2 |  |  |  | 0.000 | 0.000 |
| `haiku_batch_1step` | 1 | 346.4 | 282.4 | 0.17126860000000002 | 64838 | 22950 | 0.000 | 0.000 |

Validated run directories:

- `local_1step`: `runs/phase1_dev/hard_profile_local_smoke`
- `local_2step`: `runs/hard_profile/local_dev/hard_local_dev_2step_calibration`
- `haiku_batch_1step`: `runs/hard_profile/haiku_batch_smoke/hard_haiku_batch_smoke_1step`
