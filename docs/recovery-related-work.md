# Recovery decisions: related work and claim limits

Primary sources checked on 2026-10-22. This is a focused novelty check, not a
systematic literature review. The three closest additions below were identified
after collection started; they do not change the frozen split, policies, primary
comparison or stopping rule.

| Work | What already overlaps | What this repository must not claim |
| --- | --- | --- |
| [CodeRescue, v1](https://arxiv.org/html/2607.19338v1) | Post-failure reflect/replan/escalate actions, execution-feedback router, supervised recovery rollouts, held-out cost/success evaluation and budget calibration | That routing between repair, restart and escalation after failure is new |
| [Falsification, Not Exposure](https://arxiv.org/abs/2606.31511) | HumanEval+/MBPP+ decomposition of failed-code and feedback packets, blind resampling, shape-matched placebo controls and matched generation budgets | That separating code from feedback or adding irrelevant-context controls is new |
| [Diagnosis Before Recovery / DARC](https://arxiv.org/abs/2608.11772) | Development failure diagnosis, selective admissible interventions and a frozen verifier-selected success/cost policy | That failures should determine the recovery interface before expanding context is new |
| [Self-Debugging](https://arxiv.org/abs/2304.05128) | Reusing failed programs, execution results and feedback to improve subsequent code generation | That test-guided revision or retaining useful failed work is new |
| [Is Self-Repair a Silver Bullet?](https://arxiv.org/abs/2306.09896) | Cost-adjusted repair/resampling comparisons and model/task-dependent benefits | That repair's economic benefit needs strong retry controls is new |
| [DDBench](https://arxiv.org/abs/2608.14863) | Matched debugging-context conditions; context can help or mislead differently across models | That more debugging context can hurt is new |
| [Re-FORC](https://arxiv.org/html/2511.02130v2) | Future-reward prediction, compute allocation, stopping and model selection using reasoning-model adapters | That predicting future benefit to allocate inference is new |
| [AI Functions economics](https://github.com/strands-labs/ai-functions/blob/8f1485c2b685c83560bd91a0569cdf3af3176e75/docs/economics.md) | Experimental forecasters, verifier feedback, memory and cost-aware routing | That a probability forecaster plus value/cost rule is a novel architecture |

**CodeRescue status:** the [current arXiv record](https://arxiv.org/abs/2607.19338)
marks v2 withdrawn at ByteDance's request because submission preceded its internal
review/approval. This does not establish a technical rejection or invalidate the
priority of its disclosed recovery-routing idea. Its reported gains are author
claims from a withdrawn preprint; this repository has not reproduced them.

Our current implementation is a small diagnostic and baseline validation. It
crosses the next model with the *same task's* supplied code/feedback package,
saves forecasts before outcomes, and checks benefit prediction separately from
general success prediction. These are useful measurement choices, not an
established novel algorithm. The API forecasts do not reproduce Re-FORC or AI
Functions, and the ridge policy is not a reproduction of CodeRescue's trained
router or conformal budget calibration.

A credible next paper would need evidence that **choosing what state to transfer
adds value beyond generic post-failure model/action routing**, plus a reason that
existing methods do not already answer that question. Suitable tests include a
locked model-only versus context-only versus joint selector on an independent
task family, a stronger semantics-aware benefit predictor, realistic multi-step
state transfer, and direct comparable recovery-router baselines. Replication of
our present result is valuable even if that novelty claim does not materialize.

The earlier HumanEval+ task-versus-state predictors add code features and verifier
features together. A state advantage cannot be attributed specifically to code
information without a feedback-only prediction baseline and feature ablations.
The frozen model/context action ablations answer a different question: which
actions are useful once the same state probabilities have been computed.

The [completed MBPP+ replication](../experiments/mbpp-plus/context-value-transfer/results/replication-20261022/README.md)
now includes that feedback-only control, all twelve context/model contrasts,
and a prespecified outcome-blind API forecaster. Its primary selector advantage
is not established. Two missing solver cells leave 94/96 complete cases and
descriptive intervals. This adds external measurement evidence rather than a
validated new recovery-routing method.

Keep benchmark/product utility and scientific novelty separate: an inexpensive,
auditable benchmark can support a useful blog and integration work without
claiming a new research method.
