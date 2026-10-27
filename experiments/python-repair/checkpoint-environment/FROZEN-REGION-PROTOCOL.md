# Prospective frozen-region information calibration

Study: `repair-qwen-frozen-region-trace-development-v1`.
The final objective remains a selector that beats the strongest fixed policy on
untouched grouped bugs at equal total resources. This calibration does not meet
that objective and cannot authorize selector training.

## Intervention and sources

Test whether the saved bounded runtime trace improves full repair relative to
identical public code, instruction, tests and feedback. Use all eight original
buggy artifacts in the published acquisition preparation: scrapy-002,
scrapy-036, luigi-010, tornado-005, thefuck-022, thefuck-029, scrapy-026 and
scrapy-040. These are development-exposed original bugs after public-test
failure, **not model-generated failed repairs**. A positive result must still
transfer to generated failure checkpoints before policy development.

Source archive: `results/acquisition-preparation-20261027/evidence.zip`, SHA256
`353394a00c57f206c7f29d647ba722cc3731f1c61083bb39672f814c674f00e3`.
All eight candidates remain, including any unavailable diagnostic. No private
case, reference solution or evaluator expectation enters a request. Verify exact
source excerpts, pool identities, acquisition claims, completion seals, frozen
runtime and message projections against that immutable archive.

Two arms: `focused` and `focused_trace`. Only `runtime_diagnostic` differs within
a pair. The trace uses the already acquired function-balanced-temporal-v1
representation. Acquire **nothing again** during admission, collection or
replay; validate and use the exact saved bytes. Initial ordinary public tests
are rechecked before admission; changed public feedback stops before any call.
Candidate response evaluations are reexecuted independently after collection.

Two matched generation draws per arm per bug: **32 requests**, 16 per arm.
Both draws condition on one saved acquisition per bug. They test generation
repeatability, not robustness to independently reacquired diagnostics. Shuffle
16 task/draw pairs with seed 43139 and alternate arm order: each order occurs
eight times. Pair members share generation seed and provider settings. Verify
fresh IDs and actual bodies against all **698 historical planned bodies**,
including unsent requests. No historical controls, pooling or resumption.

## Solver and accounting

Qwen3-Coder-Next, Parasail/BF16, temperature 0.7, JSON-current contract, 8192
output-token cap, 40960 input-token reservation, price ceilings 0.12/0.80 USD
per million input/output tokens. The message-byte plus 4096 framing check is a
conservative financial admission test, not the actual tokenizer. No fallback.

Allocate **0.38 USD** under standing instructions to continue, inside the
existing **0.60 USD** cumulative ceiling. This agent-declared suballocation is
not a newly typed human amount or unlimited spending. Carry **0.20937371 USD
once**, including thirteen historical unresolved reserves, from the closed
coverage-prefix report. Each reservation is **0.0114688 USD**; all 32 reserve at
most **0.3670016 USD**. Maximum planned cumulative commitment is **0.57637531
USD**; carry plus full allocation is **0.58937371 USD**. Include all billed
failures and the larger of full reserve or trustworthy observed charge for
unknown calls. Check endpoint, key capacity and account credit read-only.

Original buggy sources have zero API generation cost. Historical carry is not
source-generation cost. Report source public verification, actual frozen
acquisition (eight acquisitions, sixteen sandbox executions), response public
verification and research-only evaluator verification separately. Charge the
saved diagnostic per planned treatment deployment in the counterfactual
resource table (sixteen acquisitions, thirty-two sandbox executions); do not
rebill cached research preparation. Diagnostic timing includes selection and
execution. Prompt projection, other preparation and full deployment overhead
remain to be measured by a later policy runner. Local seconds are not dollars.
Equal per-call limits do **not** establish equal total resources or spending.

## Transport and terminal-only analysis

Use existing independent streaming: 8 MiB wire cap, 180-second socket idle
timeout and 300-second wall check at read boundaries, at least 60 seconds between
new requests. A completed receipt needs validated identity, final usage and
DONE. Billed unusable responses remain failures. Preserve unknown reserves;
allow only the next never-admitted scheduled cell after a recorded 120-second
cooldown for the existing allowlisted no-receipt network errors. At most seven
such continuations; eighth total or third consecutive error stops. Every other
error stops. No retry, resumption, successor, substitution or key rotation.
No outcomes, arm statistics or screen reads before a terminal record.

Full success requires all public and evaluator tests. Retain all 32 selected
cells, failures, malformed responses, public false acceptances, public-score
regressions, costs and missing outcomes. Primary: `focused_trace_minus_focused`.
For a complete uncapped bank compute the mean of eight per-bug differences in
success fraction. Provide a **descriptive** 10000-resample bug bootstrap with
seed 43140 and percentile indices 249 and 9749. Two draws are not two bugs.
No p-value, generalization, scaling or causal cross-study comparison.

For an incomplete bank all mean/bootstrap fields are null and the gate is
`inconclusive_incomplete_bank`, even if finite bounds look favorable. Report
selected-cell bounds [(sT-sC-mC)/16, (sT+mT-sC)/16], not confidence intervals.
Preserve unknowns; missingness is not assumed random. A cap overrun is always
inconclusive. Show monotone binary completion extremes without imputing data.

The development screen requires a complete uncapped bank and all of:

1. At least three bugs with full trace-arm success in both draws.
2. At least four net extra trace-arm successes.
3. Positive net trace advantage separately in each draw.

Passing permits only a separate generated-failure calibration, not selector
training. Failing requires revisiting the intervention before fitting a selector.

## Freeze and delivery

Before admission: review source, exact requests, leakage and cost controls;
pass the full workflow and CI on the exact clean source commit; create an exact
packet/freeze and a single-use study claim. All historical collectors stay
closed. After terminal state audit every receipt, prompt and ledger entry;
export inert frozen sources; reproduce the full analysis and every saved model
artifact evaluation in the native sandbox. Validate saved acquisitions without
reexecution, preserving stochastic values. Any figure must match the report
and be visually inspected. Raw wire bytes are not archived.

Implementation: `vao.repair.region_information_study`, `contract_collection`,
`contract_progress`, and `vao.analysis.repair_region_information`.
Commands: `scripts/prepare_repair_region_information.py`,
`scripts/collect_repair_contract_probe.py`,
`scripts/check_repair_contract_progress.py`,
`scripts/report_repair_region_information.py --export-evidence`, and
`scripts/verify_repair_contract_evidence.py`.
