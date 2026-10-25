# Sequential Model Decisions

## Research question

After observing a verifiable task's execution history, which additional action
is worth its incremental cost: continue, restart, switch models, or stop?

The immediate question is narrower: **after visible failure, is the previous
artifact useful to the next solver, and can its value be forecast before another
attempt?** The [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md)
separates code from verifier feedback in matched conditions for 9B and 27B,
and records task-only/state forecasts before any branch outcome. It evaluates
zero-shot forecasts, not a learned policy.

The first inexpensive API pilot uses HumanEval+ coding tasks and public-example
feedback; AutoResearch/CIFAR-10 remains a subsequent transfer environment.
Completed studies supply baselines, not validation of an adaptive policy. The
[OpenRouter pilot](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md)
defines a frozen one-checkpoint protocol and cost-limited runner.

## Observable state and actions

Take decisions at explicit edit/verify checkpoints. Record the task, current
artifact and hash, visible interaction context, verifier feedback, recent
progress/errors, current model, usage so far, and remaining budget.

| Action | Operational meaning |
| --- | --- |
| Continue | Another iteration from the current artifact and available context |
| Restart | A fresh attempt from the declared initial state |
| Switch fresh | A different model starting from the declared initial state |
| Switch with context | A different model receiving a specified artifact/history package |
| Stop | End with the verified result in hand, or record an unsolved outcome |

For closed-model APIs, continuation means continuing an observable workflow.
It does not imply access to hidden chain-of-thought or clonable internal states.
Every backend must document what state can actually be preserved.

## Objective and accounting

Compare success-versus-cost and success-versus-latency curves under fixed
budgets. A finite-value objective may use expected verified reward minus total
cost; a reliability requirement may instead minimize cost subject to a declared
success target. Specify the objective before collecting evaluation outcomes.

Charge input/output/cache usage, context preparation and transfer, model or
forecaster calls, and verifier compute. Distinguish measured billing from price
estimates. Record provider/model versions and the pricing assumptions. Keep
latency and monetary cost separate unless an explicit conversion is declared.

The next-action decision compares future benefit with incremental future cost.
Past spend constrains the remaining budget and can inform task difficulty.
Also report the cost of collecting data and selecting/training the policy.

## First experiment

1. Choose one task family, two candidate models, success criteria, budgets,
   and checkpoint positions in advance.
2. Save reproducible artifacts and visible contexts at checkpoints.
3. Collect repeated, matched continuations for the allowed actions. An
   unobserved handoff cannot be scored by substituting a separate full run.
4. Fit a simple predictor of success/cost from observable state and compare
   against unconditional estimates before adding a learned forecaster.
5. Compare a strong fixed model, restart schedules, fixed escalation, and the
   proposed policy on held-out tasks. Keep policy tuning off the test split.
6. Report calibration, verified success, total cost, latency, uncertainty, and
   behavior on failures. Include abstention and budget exhaustion explicitly.

Relevant versus shuffled context should be matched for length when testing the
value of information. Context reuse can help or hurt; count its input and
preparation cost. Preserve a clear boundary between evaluation-only diagnostics
and feedback exposed to a running agent.

## Metrics and theory boundaries

First verified success, success probability at a budget, and cost to termination
are observable outcomes. Include unsolved/censored cases; do not compare only
successful runs. A time-to-90%-success quantile is not a p-value or automatically
the theoretical proper time. Report when a target is not reached within the
measured budget.

The existing theory anchor motivates hypotheses under its assumptions; do not
force task-mode labels or action-frequency histograms into an exact universal
decomposition. State-dependent failures and context transfers require an
explicit dependency model before invoking index-policy optimality guarantees.

## Related work and implementation status

- [Re-FORC](https://arxiv.org/html/2511.02130v2) already studies future-reward
  prediction, stopping, model selection, and allocation across reasoning traces.
- [AI Functions economics](https://github.com/strands-labs/ai-functions/blob/8f1485c2b685c83560bd91a0569cdf3af3176e75/docs/economics.md)
  supplies experimental cost-aware routing and forecaster/memory baselines.

This repository does not claim these ideas as new. Its proposed experiment tests
observable verifier feedback and artifact/context transfer in edit/verify loops.
The context-value diagnostic implements a prospective zero-shot API forecaster.
A calibrated learned forecaster and learned controller remain to be developed
and validated. The one-checkpoint pilot collected matched handoff outcomes on two failed states;
its development pilot is not a held-out evaluation of an adaptive controller.
