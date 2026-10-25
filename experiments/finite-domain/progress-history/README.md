# Does progress history predict the value of keeping failed work?

**Status: offline development prototype and draft design, 2026-10-25. No model
responses, funded collection, fitted predictor, frozen evaluation or empirical
gain.** Existing campaigns are complete; their remaining ceilings are not a new
authorization. The fixture configuration is explicitly not a collection freeze.

## Question and falsifiable objective

Can the observable progress history of a failed agent predict **the difference
between continuing and restarting**, beyond task, current artifact, latest
feedback, attempt count and consumed/remaining budget?

For checkpoint s and residual cap B, the target is
`Delta(s,B) = P(exact success | continue,s,B) - P(exact success | restart,s,B)`.
Collect both branches from the actual saved checkpoint, with repeated independent
API draws. A predictor of general task difficulty, a correlation with success,
or a positive hindsight oracle is insufficient evidence that history helps choose
an action. API draws need not be independent in practice: record provider/time
blocks, randomize request order, and retain task clustering.

The eventual product objective is more verified solutions at the same declared
API budget, counting selection overhead. The primary incremental-history contrast
must compare a history-aware selector with the matched current-state-only
selector. Both also need comparison with the strongest development-selected fixed
action: beating a fixed action alone cannot establish the value of history.
A proposed practical target is +5 percentage points for the incremental-history
contrast, with a paired 95% interval excluding zero on fresh tasks. Freeze the
sample-size calculation, baseline quality gates, exact comparison and decision
threshold before that evaluation;
this document is not a claim that the target is powered or achievable.

## Why a controlled environment first

The complete BigCodeBench study did not establish its primary escalation gain.
Its weak public tests and conservative admission complicated interpretation.
This prototype removes public-test false positives **relative to its own oracle**:
the verifier checks all 256 possible pairs of integers `x,y` in `0..15`.

Each generated task states a complete piecewise arithmetic/XOR specification.
The agent must implement it as a bounded Python expression. A separate ordinary
Python reference supplies expected outputs; a typed AST interpreter evaluates
the candidate without `eval`, `exec`, imports, calls or arbitrary Python execution.
Acceptance requires agreement on every input. Semantic failure exposes the number
of failing inputs and one deterministic counterexample; format failure is a
separate status with no invented semantic error count. Exact success stops the
trajectory. All these public feedback fields are available to both actions.

This is a **synthetic expression-programming microbenchmark**, not general Python
repair. It may be too easy, have uninformative progress, or poorly transfer to
real software. Development calibration must establish natural, recoverable model
failures before spending on evaluation. Do not fabricate failures, tune on held-out
outcomes or claim that fresh random constants rule out template familiarity.
Exhaustive checking does not prove that the reference specification is bug-free.

## What is executable now

From the repository root, without credentials or a GPU:

```bash
uv run python scripts/prepare_progress_history.py
uv run python scripts/prepare_progress_history.py --output runs/progress-history-development
```

The first command prints a plan. The second requires a fresh output directory
and creates eight deterministic development tasks, exact reference checks,
handwritten failed candidates, checkpoint features and paired request payloads.
The script has no live mode. These fixtures are engineering tests, not LLM results;
their zero charges and illustrative budget must never be used in an efficacy plot.
The outputs include oracle material for local engineering: **only the allowlisted
`branch_requests[action].messages` may be projected to a future solver**.

Code: `src/vao/decisions/progress_history.py`.
Checks: `tests/vao_runtime/test_progress_history.py`.
The emitted `summary.json` says `offline_fixtures_only`; it is not a finished
collection bank and must not trigger the historical research automation.

## Matched intervention and information controls

| Component | Continue | Restart |
| --- | --- | --- |
| Task, model, provider, sampling settings | Identical | Identical |
| Latest exact-verifier feedback | Identical | Identical |
| Current failed expression | Included | Omitted |
| Earlier messages/code/feedback | Omitted | Omitted |
| Residual API cap and admission rule | Identical | Identical |

“Continue” means artifact-preserving regeneration in a stateless workflow, not
resuming hidden model reasoning. “Restart” retains the latest feedback; it is
not a no-feedback arm. The shared instruction is identical; the current candidate
is the only user-payload difference. Record and charge its extra input tokens.
The two actions may consume different amounts under the same cap; report both
admission utilization and realized spending. Randomize/interleave paired draws;
never reinterpret one independent full run as an unobserved continuation.

The future **current-state baseline** receives task text, current expression,
latest feedback, attempt count, spend and remaining budget. The **history addition**
contains only the ordered public error counts/statuses and per-attempt costs.
It does not introduce previous counterexample answers, old code, hidden tests,
task IDs or future branch outcomes. Both forecasts must be saved before revealing
branch outcomes. History is predictor input, not additional solver context;
testing the causal effect of supplying a solver with its history is another study.

There is an important sufficiency limit: with a fixed stateless model and sampling
law, identical current requests have the same outcome distribution regardless of
their earlier history. Thus history cannot add intrinsic information beyond an
exactly known full request-to-outcome law. The test is whether cheap progress
summaries improve a **finite-data, limited-compute forecaster** of that law on new
tasks. Match predictor capacity/training data, charge feature/forecast overhead,
and do not turn an empirical forecasting gain into a claim about hidden memory
or a violation of this conditional independence. The offline tests explicitly
check that different histories with the same current state give identical solver
messages.

## Staged experiment, with explicit stop conditions

1. **Offline qualification (this change).** Check exact verification, unsafe-input
   rejection, semantic identities, information projections and accounting fields.
   Handwritten fixtures do not establish any recovery effect.
2. **Small, separately funded development pilot.** Start with one model/provider
   and generated task family. A planning candidate is 12 tasks, at most four
   prefix attempts, checkpoints after attempts 2/3/4 if still failing, and three
   draws per action at each checkpoint: at most 264 calls. Branches initially use
   one bounded response; there is no operational adaptive controller. Natural
   successes stop the prefix; keep all assigned tasks, including those with no
   failed checkpoint. Confirm both prompts fit the same cap before admission.
   Investigate ceiling/floor effects, stable verification, natural progress and
   recoverability. If the intervention gives no useful signal, stop and report
   it; do not build a selector to rescue a null result. These are planning counts,
   not an authorization or a frozen collection design.
3. **Intervention validation on fresh tasks.** Freeze generation, checkpoint
   schedule, repeated branches, API cap, provider settings, primary contrast and
   task-level power analysis after development. Estimate keep-minus-restart
   benefit and its uncertainty from matched branches, weighting tasks equally
   rather than over-weighting long failures. Distinguish stable action differences
   from finite-draw noise. Conditional failed-checkpoint effects are not full-task
   deployment gains. Retain missing outcomes and worst/best-case bounds.
4. **History prediction and selection only after a useful intervention.** Fit
   identical simple model classes with current state vs current state + history,
   using task-grouped cross-validation within development. Report incremental
   prediction of *branch benefit* as well as calibration of each action, and
   compare with fixed continue, fixed restart and a development-chosen rule.
   All data inspected in stages 2/3 become development. Freeze weights and policy,
   then evaluate on another fresh task set; include prefix, forecast, failed-call,
   and transfer charges in deployment costs. Report verifier time and wall time
   separately. Only this stage can support a selector-benefit claim.

The task identity is the hash of its complete truth table, so equivalent
specifications belong to one group. Exclude previously exposed identities across
splits; every checkpoint, action and replicate of a task remains in the same
partition. Parameter-disjoint evaluation does not establish new-family transfer;
an independent task family and a second model are later replications.

## Required before a paid pilot or evaluation

- New explicit campaign cap and isolated output directory; no reuse of closed
  campaign credit. Choose the exact model/provider and verify current prices.
- Immutable config and source hashes, full task manifest and semantic duplicate
  screen, sampling/output limits, balanced admission rule, randomized request
  order, checkpoint schedule and declared stopping/missing-data rules.
- Collector and audit implementation: reservations before requests, known charges,
  unknown requests kept at full reservation with no automatic retry; prompt
  provenance, responses, all failures, timings and local verifier accounting.
- For evaluation: development-only power planning with task-cluster uncertainty,
  specified estimand and multiplicity handling. Three draws do not create three
  independent tasks. No selective reporting or treatment-driven early stopping.

Re-FORC and AI Functions already motivate reward prediction and economic routing;
see the [related-work boundaries](../../../docs/decision-protocol.md#related-work-and-implementation-status).
Observable progress history plus matched artifact-preserving branches is the
hypothesis to investigate, not an established novelty or result.
