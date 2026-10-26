# Gemma 3 27B capability control

Both complete initial-repair calibrations failed the unchanged engineering gate.
The 12B produced usable source more often than the 4B, but its two full successes
were on the same development bug. This separately frozen control asks whether
27B can supply successful repairs across enough bugs to justify a later matched
continue/restart calibration. It is not a size-curve study or a selector trial.

The user's instruction “Non farti problemi di denaro. Continua.” authorizes
continued bounded research. Before any call, the agent declares a **$0.13 study
sublimit** under the existing **$0.60 cumulative ceiling**, not a new amount
separately typed by the user. No unlimited spending or historical-budget reuse
is inferred. Every prior study remains closed with its outcomes and reserves.

## Frozen design

- Study `repair-contract-gemma27b-v1`: the same twelve development-exposed BugsInPy
  adaptations, three contracts (`json_current`, `json_example`, `python_text`),
  one new initial repair per cell: 36 responses planned. No task removal.
- Pin `google/gemma-3-27b-it`, `deepinfra/fp8`, provider DeepInfra, **FP8**. The
  [public endpoint listing](https://openrouter.ai/api/v1/models/google/gemma-3-27b-it/endpoints)
  checked on 2026-10-26 supports the required parameters. The Novita BF16 route
  does not list `response_format`; it is not a substitute for this protocol.
  FP8 differs from the completed 4B/12B BF16 runs. Report the precision confound;
  do not attribute differences purely to parameter count. Pretraining data,
  sampling and collection time also differ between sizes.
- Keep every task/contract message byte-identical to both completed DeepInfra
  banks: specifications, initial buggy files, public tests/feedback and examples.
  Keep strict decoding, public and evaluator tests, temperature 0.7, maximum
  4,096 output tokens and conservative 32,768 input-token admission bound.
  Only model/route/precision, price limits, study identity and seed change.
- Seed 43121 fixes a new task order with balanced format positions. Pair the
  three formats' seeds within each bug; provider seeds do not guarantee matched
  random draws across models. All attempt identities are new, not retries of
  any old known or uncertain request.
- One sequential collector, minimum ten seconds between dispatches (same as
  12B). No retry, resume, fallback, key rotation or automatic pacing change.
  On an error preserve the uncertain reserve and stop; all unobserved cells
  remain missing. No inspection of treatment outcomes until terminal status.
- Freeze clean committed source, exact packet, funded configuration and hash of
  the complete 12B report. Validate byte-identical messages and disjoint admission
  identities before launch; verify initial public feedback locally. Keep the
  single-use study claim and durable request/reservation/receipt journal.

## Unchanged gate and next decision

For a complete bank, a contract needs at least three distinct fully solved bugs,
ten artifacts with valid syntax and the declared entrypoint, and two such valid
artifacts still unsolved. Qualifying contracts rank by full successes, then lower
actual API cost, then declared contract order. An incomplete bank is inconclusive.
This is a prespecified engineering threshold, not statistical evidence of emergence.

Report every cell, format failure, regression, false positive and null result.
A passing gate permits preparation of a separately frozen recovery experiment;
it does not establish reproducible action complementarity or authorize fitting
this selector. A failed gate requires further diagnosis of task solvability and
artifact interventions, keeping this failed bank intact. Do not relax the gate,
change prompts or hide hard tasks to turn this control into a success.

No result from twelve inspected bugs with one draw per format establishes a
held-out benefit, scaling exponent or phase transition. Do not pool protocols
or count the 36 outputs as 36 independent bugs. Future cross-size evaluation
requires repeated draws and common-checkpoint versus natural-failure analyses.
Local timing is separate; 4B used slower pacing and elapsed run times do not
measure model speed. API limits are not equal to actual spend or local cost.

## Budget and delivery

Price ceilings are $0.08/million input and $0.16/million output tokens.
Reserve **$0.0032768 per request**, **$0.1179648** for all 36, under $0.13.
Carry **$0.01760731** exactly once from the complete 12B report, including every
older charge and five unresolved reserves. The maximum design commitment is
**$0.13557211**; the study-cap envelope is **$0.14760731**, below $0.60.
The launcher checks endpoint identity, current prices and credit before any
model generation. No credential may be printed or written into the evidence.

After completion/interruption, audit the whole ledger, requests and receipts;
export inert source and evidence, reproduce JSON/Markdown after isolated
extraction and independently re-execute saved artifacts in the OS sandbox.
Keep accounting, missingness and precision limitations in the report. Update
PR 20, repository indexes and offline checks; verify exact-head CI. The final
continue/restart selector objective remains open irrespective of this gate.
