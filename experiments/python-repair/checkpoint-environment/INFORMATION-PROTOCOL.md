# Public trace information probe — prospective development protocol

Study: `repair-public-trace-information-v1`. Written before any response in this
new study. This implements the [user-directed goal amendment](GOAL-AMENDMENT-20261026.md).
It tests a diagnostic intervention that might later support a cost-aware selector;
it does not replace or claim completion of the broader recovery-policy objective.

## Question and controls

After a saved Gemma 27B repair fails a public test, does exposing a bounded trace
of that failed execution increase the chance that the next repair passes both
public and evaluator suites? The primary contrast is **focused trace minus
focused same-information feedback**. Existing raw feedback is a secondary control.
No favorable secondary contrast may replace a null primary.

The three conditions share the complete candidate files, instruction, public
case list, latest public results, model/endpoint/precision, output contract,
output-token limit and per-call allowance:

1. `raw`: the existing public feedback.
2. `focused`: the same information plus a repetition of the first failed public
   case, its expected outcome and observed result. This is a presentation control.
3. `focused_trace`: the same focus plus bounded intermediate candidate states
   observed while executing that public case. This is additional execution
   information, not an expected trace, reference patch or hidden-test diagnosis.

Prompts differ in length, so identical limits do not mean identical billed costs.
This one-call information contrast is not yet an equal-total-cost policy test.

## Fixed population and checkpoint source

Take exactly the twelve `json_current` artifacts in the complete 27B archive
`f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913`.
That output contract did not pass the old engineering gate; choosing it here is
a declared convention for a diagnostic study, not a retroactive qualification.
Every source is hash-checked and its public outcomes reproduced.

Eight artifacts fail a public test and are eligible. Four pass publicly and
receive no new calls; all four remain in the task table, with their original
full-suite outcomes shown only in analysis. In particular, the known timestamp
ambiguity remains documented without rewriting the task, changing historical
scores or selecting probes using evaluator feedback. These are twelve already
inspected development bugs, ten from youtube-dl, not fresh or representative
evaluation data. The conditional estimand concerns the eight eligible states.

No new prefix is generated. The source prefix is the saved 27B call; its real
cost is retained. Each condition receives **four draws from the same checkpoint**,
with no within-arm progression or feedback from another draw. Thus eight bugs ×
three conditions × four draws = **96 requests**. Replicates do not create 32
independent bugs. All arms and replicates stay grouped by underlying bug.

## Diagnostic and generation settings

Use the existing public-only adapter: first failure in declared suite order,
ordinary re-execution plus one instrumented execution, both agreeing with the
saved public outcome. At most 32 recent events / 12,000 event bytes from the first
512 captured events; eight bounded locals per event. Limits and omitted values
are explicit. A missing, inconsistent or disabled trace yields an unavailable
marker, not dropped eligibility or an invented fact. Reproduce every prepared
diagnostic before provider preflight. Drift stops launch without retuning.

Provider: OpenRouter, `google/gemma-3-27b-it`, `deepinfra/fp8`, DeepInfra, FP8,
temperature 0.7, maximum 4,096 output tokens, 32,768 input admission ceiling,
JSON object mode, no fallback. Base seed 43122. A distinct deterministic seed is
derived for each bug/draw and shared by all three arms; provider determinism and
common random numbers are not guaranteed. Bug/draw triples are shuffled once;
the six condition orders are rotated in seeded order. Requests are admitted at
least ten seconds apart. Bodies, order, checkpoints and seed values are frozen
before any paid request. There is no model switch or adaptive selection.

## Declared budget and accounting

The user authorized continued research (“Non farti problemi di denaro. Continua.”)
and explicitly requested the research-goal amendment and implementation. Under
that instruction the agent declares a separate **$0.34 sublimit**, retaining the
existing **$0.60 cumulative ceiling**. This is an agent-declared bounded allocation,
not a newly user-typed dollar authorization and not unlimited spending.

Price ceilings: $0.08/M input and $0.16/M output tokens, verified against
[OpenRouter](https://openrouter.ai/google/gemma-3-27b-it) and checked again with
endpoint metadata at launch. Reserve $0.0032768 per call; all 96 reserve at most
$0.3145728. Carry **$0.02211715 exactly once**, including the five older unresolved
reserves. The maximum design commitment is **$0.33668995**, and the cap envelope
is **$0.36211715**, both below $0.60. Earlier MBPP/BigCode campaigns remain closed
and do not fund this study.

The cumulative ledger counts actual new charges plus all uncertain reserves.
It does not re-bill old prefixes. In analytical per-deployment comparisons,
each bug/draw/arm pays its source prefix once, the new response, public checks,
and any diagnostic acquisition; distinguish this counterfactual cost allocation
from the real account ledger. The trace was cached for experimental preparation,
but a deployed trace policy is charged two local probe executions per decision.
Report public/response verification time, probe counts and wall time separately;
do not invent a local-compute-to-dollar conversion. No claim of equal realized
spending or total-resource superiority is permitted from this probe.

## Frozen outcomes and analysis

The outcome is one candidate passing **both entire finite suites**. Preserve
malformed output, public regressions, public-pass/evaluator-fail cases, provider
errors, missing responses and paid-but-unscored calls. A malformed paid response
is observed unsuccessful; a missing response is unknown. The secondary public
test fraction assigns zero to an invalid artifact by convention, not because
unevaluated tests ran and failed.

At terminal completion/interruption, run the shared receipt/request/cell audit
and `scripts/report_repair_information_study.py`. Report all twelve source states,
each arm's 32 planned responses, successes, missingness, false positives,
regressions, exact costs and per-bug results. For incomplete banks, show worst/best
assignments to missing outcomes for each selected-arm rate and paired difference;
do not estimate a complete-bank mean or bootstrap interval from survivors.

For a complete bank, report mean paired per-bug success-rate differences and
10,000 paired bug-bootstrap draws with seed 43123, using sorted endpoints 249
and 9749. These are **descriptive intervals with eight selected clusters**,
not confirmatory inference; no p-values or a scaling-law fit are planned.

The prospective engineering screen requires all of:

- the complete 96-response bank without a financial overrun;
- at least three distinct bugs with at least two of four full successes in
  `focused_trace`;
- at least four more full successes in `focused_trace` than `focused` (12.5
  percentage points across 32 draws);
- a positive trace-minus-focus success difference in both predefined halves
  (draws 0–1 and draws 2–3).

These practical criteria demand repeated, multi-bug improvement rather than an
isolated lucky output; they are not a statistical significance threshold or
proof of action complementarity. Passing permits design of an independent
acquisition calibration, **never automatic selector training**. Failing retains
the null result and stops this intervention's escalation. No threshold, contrast,
task list, prompt or draw count changes after outcomes.

## Execution and delivery rules

Commit the source/config/protocol, pass offline checks and CI, prepare a packet
matching that source, inspect exact projections, and create a source freeze.
The shared collector checks credit, pinned endpoint parameters/prices, clean
source, source archive, diagnostics and a durable single-use study claim before
admission. No automatic retry/resume, duplicate output directory, key rotation,
provider fallback, or second study under this identity. Any uncertain request
retains its reserve and stops collection. No treatment statistics while active.

After terminal collection: reproduce the report from an isolated hash-checked
archive, independently re-execute all saved artifacts and public diagnostic
projections, preserve inert frozen sources, and update PR 20 with limits and
nulls as prominently as positive findings. Historical sources remain unchanged.
