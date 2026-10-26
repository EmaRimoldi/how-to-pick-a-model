# Coding-solver compatibility control

Status: **complete_development_solver_probe**. Gate: **candidate_for_separate_intervention_calibration**. No selector trained.

Responses: 32/32; full repairs: 10; missing: 0.

Study commitment: $0.01816000 / $0.24; cumulative: $0.06942739 / $0.60.

| Development checkpoint | Eligible | Received | Full repairs | First / second half successes |
| --- | --- | ---: | ---: | --- |
| development/bugsinpy-adapted/youtube-dl-003 | True | 4 | 0 | [0, 0] |
| development/bugsinpy-adapted/youtube-dl-011 | False | 0 | 0 | [0, 0] |
| development/bugsinpy-adapted/youtube-dl-013 | True | 4 | 3 | [2, 1] |
| development/bugsinpy-adapted/youtube-dl-020 | True | 4 | 1 | [1, 0] |
| development/bugsinpy-adapted/youtube-dl-027 | False | 0 | 0 | [0, 0] |
| development/bugsinpy-adapted/youtube-dl-031 | True | 4 | 2 | [1, 1] |
| development/bugsinpy-adapted/youtube-dl-032 | False | 0 | 0 | [0, 0] |
| development/bugsinpy-adapted/youtube-dl-033 | True | 4 | 3 | [1, 2] |
| development/bugsinpy-adapted/youtube-dl-042 | True | 4 | 0 | [0, 0] |
| development/bugsinpy-adapted/youtube-dl-043 | True | 4 | 1 | [1, 0] |
| development/bugsinpy-adapted/httpie-005 | True | 4 | 0 | [0, 0] |
| development/bugsinpy-adapted/tornado-009 | False | 0 | 0 | [0, 0] |

## Descriptive summary

```json
{
  "planned": 32,
  "observed": 32,
  "successes": 10,
  "missing": 0,
  "success_bounds": [
    0.3125,
    0.3125
  ],
  "mean_success": 0.3125,
  "descriptive_bug_bootstrap_95": [
    0.125,
    0.53125
  ],
  "usable_sources": 26,
  "public_passes": 11,
  "false_positives": 1,
  "regressions": 11,
  "public_improvements": 15,
  "edit_categories": {
    "exact_copy": 0,
    "format_or_comment_only": 2,
    "entrypoint_only_syntax_change": 0,
    "other_syntax_change": 24,
    "unparseable": 5,
    "no_artifact": 1
  },
  "known_usd": "0.01816000",
  "committed_usd": "0.01816000",
  "counterfactual_prefix_usd": "0.00439680",
  "source_public_verification_seconds_if_deployed": 9.628027495928109,
  "response_verification_seconds": 19.685167546849698,
  "provider_elapsed_seconds": 335.3503584166756
}
```

## Limitations

- One model/endpoint configuration on eight previously exposed failure checkpoints, with four draws; twelve source records retained.
- Historical Gemma responses are not concurrent paired controls. Model, provider, precision, seeds and time differ; no scaling or model-causality claim.
- This checks solver compatibility, not action complementarity, acquisition benefit or an equal-budget policy advantage.
- No trace, reference patch, expected hidden value or extra editing cue is supplied. Original instructions and raw public feedback are unchanged.
- Incomplete banks keep all selected cells and finite missingness bounds; mean/bootstrap/gate remain unavailable.
- Complete-bank bootstrap intervals resample eight bugs and are descriptive, not evidence for an untouched population.
- Every counted repair passes public and evaluator suites; this does not prove correctness on all possible inputs.
- Prefix cost is counted once per counterfactual deployment and not rebilled into the actual ledger. Local runtime and provider latency are separate.
- A passed screen permits only a separately frozen intervention study. No automatic selector fitting or further calls.
