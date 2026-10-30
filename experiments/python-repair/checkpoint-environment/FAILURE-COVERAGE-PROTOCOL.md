# Natural-failure diagnostic coverage: development protocol

Status: prospective protocol before any new model call. This is a difficulty and
intervention calibration, not a selector evaluation. Historical studies, outcomes,
missingness and screens remain immutable. No inference about model scaling.

## Cohort and information boundary

Use exactly the six tasks, in pool order, in `development-broader/pool.json`
(SHA-256 `a391412193749cf6b3c20472cdb703f27fc97c222edcea4b6a77165bfa8e006b`).
All are already exposed development cases across four projects. Retain all six
through reporting; never add or replace a task based on model outcomes. Reference
fixes and evaluator cases never enter prompts, trace selection or continuation
eligibility. All arms know every public input, expected value and public feedback.

## Stage 1: one initial repair per bug

Use Qwen3-Coder-Next, Parasail/BF16, temperature 0.7, 4,096 maximum output tokens,
25,600 input-token reservation, JSON file contract and streaming with an 8 MiB
wire limit. Seed namespace 43138; the existing provider adapter derives a request
seed from namespace, trajectory, phase and depth. One request per minute, no
fallback, key rotation, retry or continuation after an interrupted collection.
Exact requests and six-task order are frozen before dispatch. Use the original
buggy files and complete original public feedback, with the existing focused
public-failure duplication. No runtime trace in this stage.

Retain valid outputs, syntax errors, invalid output contracts, public false
acceptances and missing requests. Only a decoded file artifact with at least one
failed public test defines a natural recovery checkpoint; syntax errors qualify
if the artifact decoded and the public verifier reports failure. An invalid
container is a recorded protocol failure, not a fabricated replacement file.
Public-pass artifacts stop even if evaluator tests fail. Private outcomes cannot
turn an apparent success into an agent-visible recovery trigger.

Stage 2 is permitted only if Stage 1 is complete within budget and at least three
of the six original bugs have natural artifacts failing at least two public test
cases. Otherwise report insufficient failure-coverage headroom and stop this
study. This is a difficulty gate, not evidence that a diagnostic is useful.

## Stage 2: matched recovery interventions

On every valid public-failing artifact from Stage 1 (including one-failure cases),
collect three matched draws in each of these fixed arms:

- `direct`: current code plus complete public feedback;
- `first`: same information plus a trace of the first failing public case;
- `all`: same information plus traces of all currently failing public cases.

The system text and public core are identical. Public order selects cases;
acquisition is bound to the exact new artifact and freshly verified feedback.
The six-case bound, ordinary-versus-traced consistency check, value-preserving
trace encoding and explicit unavailable records use the published coverage
component. No evaluator-derived hints, adaptive trace selection, salvage or
prompt truncation. Each trace costs one ordinary and one traced execution.
Unavailable selected traces remain unavailable in the corresponding prompt.

Seed namespace 43139; order bug/draw blocks using Random(43139), then rotate
through the six arm permutations shuffled by Random(43140). Matched arms share
the provider seed within a bug/draw block. Provider seed support is not a promise
of deterministic or independent sampling. Freeze all derived requests before
any Stage 2 dispatch. If any message exceeds the declared byte-plus-framing
input bound, preserve every proposed cell and stop before Stage 2 admission;
report admission infeasibility rather than shorten inputs or drop that bug.
At most 54 recovery requests, 60 total. No interim treatment summaries.

## Outcomes and decision fixed before Stage 1

Full repair requires both public and evaluator suites. Report all six initial
outcomes, public false acceptances, format errors, per-bug and per-draw recovery
successes, regressions, known costs, unresolved reserves and all missing cells.
Primary recovery contrast: `all` minus `first`. Required secondary: `all` minus
`direct`; retain `first` minus `direct` regardless of sign. Primary denominators
are all triggered bugs × three draws, never successful or trace-available cases
only. Also report end-to-end outcomes over all six original bugs, counting a
public-pass/private-fail prefix as unresolved under every deployable arm.

A useful-intervention screen requires a complete initial and recovery bank,
at least three bugs repaired by `all` in at least two of three draws, and strictly
positive net success differences in **each draw against both controls**. This
implies at least three net extra successes against each control. Missingness,
admission failure or interrupted collection makes the screen inconclusive;
keep finite worst/best bounds on selected cells, without imputation. With six
purposively selected bugs and four project groups, report descriptive counts
and differences only, no significance claims or confidence-interval gate.

A passed screen only permits designing an independent replication. It never
permits immediate selector training or claims of generalization. A failed
screen requires revising the intervention, not swapping the primary contrast.

## Accounting and delivery

Retain $0.20640271 once from the closed campaign, including thirteen uncertain
reserves. Allocate at most $0.04 to Stage 1; conditionally plan at most $0.35 to
Stage 2, within the unchanged $0.60 campaign cap. The combined allocation would
be $0.59640271 including carry. At price ceilings $0.12/$0.80 per million tokens,
each call reserves $0.00634880; 6 + 54 calls reserve $0.38092800. Recheck actual
endpoint settings, support, price ceilings and credit before dispatch. Stage 2
requires a separate tested implementation and exact frozen packet, consistent
with this protocol and with terminal Stage 1 accounting. No duplicate collection.

Record prefix, acquisition, inference, verification and uncertainty separately.
For end-to-end arm accounting charge the shared prefix once per deployed bug,
not three times, while retaining the actual experimental bill for all branches.
This calibration gives equal per-call limits, not equal total policy resources.
The ultimate selector still requires untouched grouped evaluation against the
strongest fixed policy, with all diagnostic/selection/failure costs included.
Export exact requests, responses, source provenance and inert evidence; reconcile
receipts and replay public/evaluator outcomes before interpreting results.
