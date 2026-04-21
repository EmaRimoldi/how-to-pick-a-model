# Hard Haiku Batch Pilot Readout

Run: `runs/hard_profile/haiku_batch_pilot/hard_haiku_batch_pilot_3step`

- Steps: `3`
- Branch evaluations: `18`
- Total wall-clock: `807.0s`
- Total sec/step including baseline: `269.0`
- Post-baseline sec/step: `247.7`
- Total cost: `$0.600`
- Cost/step: `$0.200`
- Input tokens total: `355882`
- Output tokens total: `83089`
- Selected modes: `['layout', 'caching', 'summaries']`
- Best visible loss: `0.28242576429393895`
- Best counterfactual loss: `0.2784324758473186`
- Proposal failure rate: `0.111`
- Source-validation failure rate: `0.111`
- Incorrect branch rate: `0.056`
- Verifier infrastructure failure rate: `0.000`

Failure notes:

- Two candidates were rejected because generated code used banned `list.remove` calls.
- One `topk` branch was semantically incorrect on tie-breaking/correctness; it is logged as an evaluated counterfactual branch.
