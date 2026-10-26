# Gemma 3 4B development calibration

Status: **incomplete_development_calibration**. No fitted or held-out selector result.

84 saved responses / 88 admissions; 18/24 complete trajectories across 12 selected tasks.
Known generation charges: 0.00405203 USD; conservative commitment including unknown requests: 0.01011411 against 0.60.

Observed failed checkpoints: 15; complete matched checkpoints: 11.
Format failures: 17 ({"empty_object": 17}). Public-test false positives among all observed artifacts: 0.
Observed recovery responses: 53; full recovery successes: 0. Missing responses are excluded from these counts, not marked as failures.

Checkpoints with identical continue/restart input files: 0 (retained as controls, not evidence of a distinct artifact intervention).

![Observed response outcomes](calibration-outcomes.png)

## Per-bug coverage and action difference

C−R bounds include missing draws at observed checkpoints; they are not confidence intervals. Prefix successes refer to observed full public+evaluator passes.

| Task | Prefix success observed | Finished / planned | Checkpoints complete / observed | C−R lower | C−R upper |
| --- | ---: | ---: | ---: | ---: | ---: |
| development/bugsinpy-adapted/youtube-dl-003 | 0 | 2/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-011 | 0 | 1/2 | 5/6 | -0.083 | 0.000 |
| development/bugsinpy-adapted/youtube-dl-013 | 0 | 2/2 | 1/1 | 0.000 | 0.000 |
| development/bugsinpy-adapted/youtube-dl-020 | 0 | 1/2 | 4/5 | -0.100 | 0.000 |
| development/bugsinpy-adapted/youtube-dl-027 | 0 | 2/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-031 | 0 | 2/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-032 | 0 | 2/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-033 | 0 | 1/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-042 | 0 | 2/2 | 0/0 | — | — |
| development/bugsinpy-adapted/youtube-dl-043 | 0 | 0/2 | 0/2 | -0.750 | 0.500 |
| development/bugsinpy-adapted/httpie-005 | 0 | 1/2 | 1/1 | 0.000 | 0.000 |
| development/bugsinpy-adapted/tornado-009 | 2 | 2/2 | 0/0 | — | — |

## Prefix progress

Changes compare the generated prefix with its immediately preceding public feedback. Format errors have no score change. No-op means byte-identical supplied files.

| Task | Prefix attempts | Improvements | Regressions | No-ops | Format errors |
| --- | ---: | ---: | ---: | ---: | ---: |
| development/bugsinpy-adapted/youtube-dl-003 | 2 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-011 | 6 | 0 | 0 | 2 | 0 |
| development/bugsinpy-adapted/youtube-dl-013 | 3 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-020 | 5 | 0 | 0 | 3 | 0 |
| development/bugsinpy-adapted/youtube-dl-027 | 2 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-031 | 2 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-032 | 2 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-033 | 1 | 0 | 0 | 0 | 1 |
| development/bugsinpy-adapted/youtube-dl-042 | 2 | 0 | 0 | 0 | 2 |
| development/bugsinpy-adapted/youtube-dl-043 | 2 | 0 | 2 | 0 | 0 |
| development/bugsinpy-adapted/httpie-005 | 2 | 0 | 0 | 0 | 1 |
| development/bugsinpy-adapted/tornado-009 | 2 | 2 | 0 | 0 | 0 |

## Costed diagnostic policies

Identical common complete checkpoints for all policies; equal weight per contributing bug. Costs include the prefix once and every generated candidate, even the discarded one. Recorded local verifier timings remain in policy_rows; fresh replay-selection timings are separate machine-dependent measurements, excluded from reproducibility equality.

| Policy | Bugs | Checkpoints | Selected full success | Mean API cost | Difference from continue-one | Descriptive paired 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| continue_one | 4 | 11 | 0.000 | 0.000128 | 0.000 | [0.000, 0.000] |
| restart_one | 4 | 11 | 0.000 | 0.000126 | 0.000 | [0.000, 0.000] |
| continue_two_public_select | 4 | 11 | 0.000 | 0.000174 | 0.000 | [0.000, 0.000] |
| restart_two_public_select | 4 | 11 | 0.000 | 0.000182 | 0.000 | [0.000, 0.000] |
| mixed_two_public_select | 4 | 11 | 0.000 | 0.000180 | 0.000 | [0.000, 0.000] |

## Replication diagnostic

Strict advantage in both paired draws at the same checkpoint: {"none": 11}. A single differing draw is not a replicated action preference.

## Limits

- All tasks are inspected development adaptations; no held-out selector evaluation.
- Selected development tasks cannot establish generalization to other bugs/projects. The intended real pool has ten of twelve bugs from one upstream project.
- Policy table uses common complete observed checkpoints, averages within bug then across bugs, and can be biased by missing states.
- Missing-outcome bounds condition on observed eligible checkpoints; unobserved future states are not identified.
- Bootstrap intervals resample bug-level paired means (5000 draws, seed 261026); descriptive, no confirmatory p-values.
- All-zero samples yield degenerate bootstrap intervals; these do not bound population recovery probability or establish action equivalence.
- One versus two candidates have the same allowance but different actual spending; these are one-checkpoint diagnostics, not deployed multi-step policies.
- Public selection can choose an incorrect candidate. No evaluator oracle is used to select answers.
- Two draws and a tiny task pool do not establish learnable or generalizable action complementarity.
