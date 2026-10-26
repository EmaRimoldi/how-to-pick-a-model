# Recovery decisions: related work and claim limits

## Expanded novelty review — 2026-10-25

**Verdict: the broad research premise already has direct precedents. Neither
adaptive continue/restart/rollback/model-switch control nor prediction before
paying for another attempt is, by itself, a defensible novelty claim. The present
Python environment remains an engineering prototype, not evidence of a new
scientific method.** This review updates research framing only; it does not
amend completed experiments, authorize a collector, or discard earlier findings.

### Scope and evidential standard

This search used 52 web queries across code repair, resampling, adaptive search,
failure prediction, rollback, model switching, context transfer and classical
restart policies. It followed references backwards from Re-FORC and
FailFast–RestartSmart, checked arXiv/ACL primary records, and inspected author
repositories. Full-text checks focused on methods, comparisons, costs and
evaluation targets. The query list appears below. Retrieval finished on
2026-10-26 UTC / 2026-10-25 America/Los_Angeles.

This is an extensive targeted review, not an exhaustive systematic review with
a complete bibliographic export. Search indexing can miss work. The Hugging Face
paper-search connector was unavailable; it is not counted as a searched database.
Secondary summaries were discovery aids, not evidence for the findings below.
Results are reported by the respective authors and have not been independently
reproduced here. A preprint's existence establishes prior disclosure, not validated
performance. Confidence that the broad idea has precedents is high; absence of
every possible narrower precedent cannot be certified.

### Direct precedents

| Work / verified status | Overlap with our proposed contribution | Important boundary |
| --- | --- | --- |
| [PATSSEL: Debug or Regenerate?](https://aclanthology.org/2026.findings-emnlp.2173/) — Findings EMNLP 2026 | Chooses debugging versus regeneration. Crucially, §6.2/Table 2 also evaluates prospective TF-IDF value, SFT and preference-gap routers before candidate outcomes. | Main method generates both candidates and selects with verifier tests. Regeneration sees the problem only; debugging also sees failed code and a failing test. Thus this is not a feedback-matched code-only intervention. |
| [AB-MCTS: Wider or Deeper?](https://arxiv.org/html/2503.04412v5) — NeurIPS 2025 spotlight per arXiv record | Adaptively allocates search between fresh candidates and refinement using execution feedback. Appendix D adds adaptive model choice within the search. [TreeQuest](https://github.com/SakanaAI/treequest) is the associated library. | Main competitive-programming results evaluate chosen solutions on hidden tests. Multi-model ARC-AGI-2 results use Pass@k coverage, not final selected-answer accuracy. Generation-count budgets are not dollar-matched budgets. |
| [DARS](https://aclanthology.org/2025.acl-long.973/) — ACL 2025 | Returns to selected decision points and generates alternative actions using previous execution feedback. Evaluated on SWE-bench Lite. [Author code](https://github.com/vaibhavagg303/DARS-Agent). | Branching uses completed-trajectory information and a separate trajectory selector; this is a substantive adaptive-search baseline, not a minimal one-step patch decision. |
| [FailFast–RestartSmart](https://arxiv.org/html/2608.03222v1) — August 2026 preprint | Observable recent history predicts failure; a fresh same-model retry can inspect/apply/discard the interrupted diff as an initially disabled overlay. This directly studies salvaging edits while removing the preceding reasoning context. | Restart gets fresh budget. Failure prediction is not direct estimation of the relative value of preserving an artifact. |
| [Atropos](https://arxiv.org/html/2604.15075v1) — April 2026 preprint | Uses trajectory-graph features for early failure prediction and switches to a stronger model. | Parallel hotswap migrates ongoing contexts; sequential hotswap replaces remaining independent ensemble runs and explicitly does not migrate context. Do not conflate these two modes. |
| [Rollback-Induced Reflection / RIR](https://arxiv.org/html/2609.18304v1) — September 2026 preprint | Jointly decides when to intervene, where to restore and what knowledge to retain. Separates restored environment/context from reflection memory across ALFWorld, ScienceWorld and GAIA. | Matched interaction budgets do not establish matched token/dollar costs. Its policy-class inclusion result is not a guarantee that the implemented controller improves outcomes. |
| [AgentRewind](https://arxiv.org/html/2608.14380v1) — August 2026 preprint | Restores aligned context and workspace checkpoints and retains failure experience. Compares Continue, Restart-with-Experiences and other recovery controls on 82 MettleBench tasks. | No preset wall-time, step or total-token caps; termination instead uses five repeated identical first failures. Reported success gains do not establish an equal-dollar advantage. |
| [CodeRescue v1](https://arxiv.org/html/2607.19338v1) — withdrawn preprint | Learns post-failure reflect/replan/escalate routing from task and execution feedback, with cost calibration. | [Withdrawal record](https://arxiv.org/abs/2607.19338) cites incomplete company internal approval, not a technical rejection. Gains remain unreplicated author claims. Prior disclosure still matters. |
| [Re-FORC v2](https://arxiv.org/html/2511.02130v2) — 2025 preprint, revised July 2026 | Predicts future reward as a function of extra reasoning and uses it for stopping, model selection and compute allocation. | The cost-aware forecasting objective is already present. Moving to executable patch states must add a tested mechanism or finding, not merely rename this objective. |
| [Adaptive Inference-Time Compute](https://arxiv.org/html/2410.02725v1) — October 2024 preprint inspected | Manvi, Singh and Ermon train mid-generation self-evaluations of whether restarting will improve a response. | Already a direct precedent for prospective restart-benefit prediction; studies response generation, not restoration of code workspaces. |

**PATSSEL detail that changes the verdict:** the PDF's §6.2 explicitly tests
pre-execution action selection. Table 2's best such router scores 67.5 versus
70.4/70.6 for generated-test selection. These are micro-averaged reference-test
scores, not percentages of completely solved tasks. The headline 2.7/3.2-point
gains use gold-test routing; deployment tests are analyzed separately. Baselines
receive two candidates and comparable call counts, not demonstrated equal
realized dollar costs. Therefore neither its main-method abstract nor its headline
number should be used to claim an unoccupied prospective-routing gap.

**FailFast cost detail:** at the reported Qwen3.6-27B 25% FPR operating point,
resolution rises from 66.6% to 71.8%, but Table 3 reports +43.8% net token
overhead; cold restart reaches 66.8% with +18.2%. The separate low-FPR stopping
experiment saves tokens. These are different operating points, not simultaneous
evidence of higher success at unchanged spend.

### Additional evidence and boundaries

| Work | Why it matters / depth inspected |
| --- | --- |
| [GraphAHA](https://arxiv.org/html/2609.12757v1) | Adaptive sampling, reasoning, implementation and repair with graph-state reuse; methods and metrics checked. Its primary budget counts each LLM call uniformly. The highlighted 4.1-point gain concerns visible-test Pass@1, so it must not be substituted for held-out correctness. |
| [The Intervention Paradox](https://arxiv.org/html/2602.03338v1) | Methods and recovery/disruption accounting checked. Accurate failure prediction can still harm end-to-end success because intervention destroys otherwise successful runs. This distinction is itself established prior work. |
| [Static Evaluation of Model Switching Scores the Wrong World / Replay Gap](https://arxiv.org/html/2608.08239v1) | Methods checked; reports live counterfactual forks paired with same-model controls. Roughly 900 rollouts come from six paired runs, not 900 independent tasks. Supports rerunning the world after switching, not stitching incompatible logs. |
| [Real-Time Detection and Repair of LLM Agent Failures](https://arxiv.org/html/2608.02464v1) | §10 checked: paired checkpoint re-execution, fixed repair rungs and adaptive control. The adaptive rung does not resolve an advantage over resampling (reported p=0.61); identifying the failing check is stronger in that setup. History monitoring and paired repair controls are already studied. |
| [Repair, Retry, and the Cost of Hindsight](https://arxiv.org/html/2610.22698v1) | Abstract and experimental decomposition checked. Lean experiments separate failed proof, corresponding diagnostic and retry instruction. Feedback can compensate for anchoring without beating resampling. This is relevant negative evidence, not a universal theorem that feedback is useless. |
| [Poison Valleys](https://arxiv.org/html/2610.21514v1) | Setup checked: controlled incorrect hypotheses/plans on two synthetic Python cases built on real packages. Diagnoses how earlier commitments affect executable failures. It does not establish the effectiveness of a prospective recovery selector. |
| [Dependency-Guided Rollback Repair](https://arxiv.org/html/2608.10502v1) | Abstract and method outline checked: dependency provenance preserves unaffected work and selectively replays affected computation. Relies on diagnosed faulty memories; adjacent state-recovery evidence rather than a code-patch value predictor. |
| [Is Self-Repair a Silver Bullet?](https://arxiv.org/abs/2306.09896) — ICLR 2024 | Primary abstract/status checked: cost-adjusted repair gains vary by model and task and can disappear. Independent retries are an essential comparator. |
| [Meta-Reasoner](https://arxiv.org/abs/2502.19918) | Primary abstract/status checked: contextual-bandit guidance includes backtracking and restart. Evidence in other reasoning domains; not independently audited here. |
| [TAAR](https://arxiv.org/html/2601.11940v1) | Primary abstract inspected: trap-aware restart in long reasoning traces. An additional precedent for selecting an intervention point. |
| [Allocating Test-Time Compute Between Revision and Resampling](https://arxiv.org/abs/2610.28294) | Primary abstract inspected, October 2026: adaptive replay refinement switches from revision to resampling. Decoding-level efficiency should not be translated directly into hosted-API dollar savings. |
| [Optimal Speedup of Las Vegas Algorithms](https://www.cs.utexas.edu/~diz/pubs/speedup.pdf) | Foundational primary abstract checked, 1993. Restart schedules predate LLMs; its independent Las Vegas assumptions do not automatically hold for stateful agents or imperfect test verifiers. |

The earlier focused review below retains other relevant sources and the
provenance of the completed studies. Frameworks and logging infrastructure are
useful engineering references; their existence alone does not demonstrate a
scientific performance advantage. TreeQuest, DARS and AgentRewind should be
considered before implementing equivalent search/recovery machinery.

### What remains a candidate research question

A potentially useful empirical question is: **with a fixed observable feedback
packet and explicit remaining budget, when does retaining a concrete partial
patch improve held-out repair success over restoring the original buggy files,
and can a cheap selector exploit that difference on unseen bugs?**

This is a candidate combination of controls and setting, **not a certified
novel problem**. Prospective selection, reusable edits, matched forks and useful
history all have precedents above. A contribution would require a new reproducible
finding or a demonstrable improvement over relevant prior methods.

Our current [matched interface](../experiments/python-repair/checkpoint-environment/README.md)
changes only the supplied editable files; restart retains the same latest feedback
and restores the original buggy program, not an empty solution. This is narrower
than general conversational restart and different from PATSSEL's problem-only
regeneration. It is worth measuring, but a different prompt contract is not by
itself a paper contribution.

History must also be interpreted carefully. For a stateless solver with the same
complete request, execution state, model configuration and sampling law, an
unobserved past cannot intrinsically change the continuation distribution.
Historical signals may help a bounded predictor summarize state or infer
unobserved task properties. Compare predictors with matched capacity and data,
and describe that restricted prediction advantage rather than claiming history
creates information beyond the complete state.

### Consequences for the next experiment

1. Treat the first model pilot as replication and calibration. The twelve
   development fixtures establish harness behavior; they cannot establish a
   general recovery advantage or paper-level novelty.
2. First compare fixed continue, feedback-matched restart, rollback to a
   prespecified earlier state, and optional-diff transfer where applicable.
   Separate a preserved artifact from preserved conversation/diagnosis. Keep
   instruction-only resampling and feedback-only controls where the task contract
   permits them.
3. Evaluate relevant stronger baselines: a PATSSEL-style two-candidate verifier
   selector, a cheap prospective value router, an adaptive branching baseline
   informed by AB-MCTS, and edit-preserving restart informed by RestartSmart.
   Call any simplified port an adaptation, not a faithful reproduction.
4. Keep decision features strictly public; score full-task correctness on held-out
   tests. Record false public passes, interrupted calls and missing outcomes.
   Separate oracle action selection from a deployable policy.
5. Charge prefix work, selector/test-generation calls, longer prompts, retries
   and uncertain reservations. Report success versus actual cumulative spend and
   caps separately; report local verification time too. Extra attempts or equal
   call counts cannot stand in for equal cost.
6. Keep all checkpoints/replicates of a bug together, split by upstream project
   where feasible, and evaluate on untouched bugs after freezing the policy.
   Only fit a selector if a useful action contrast exists. A null finding about
   transfer or adaptive selection remains a valid result.

No new paid requests, collection protocol or model integration was introduced
for this review.

### Search query record

The following queries document discovery scope, not database completeness.
Backward citation checks included Re-FORC → Manvi and FailFast–RestartSmart →
Atropos / Intervention Paradox / DARS. Primary source links above are the
verified evidence set; other search hits were screened rather than exhaustively
read.

<details>
<summary>52 queries issued in this review</summary>

1. "CodeRescue" recovery code generation router
2. "Falsification, Not Exposure"
3. "Diagnosis Before Recovery" DARC
4. LLM code repair restart resample continue adaptive debugging budget paper
5. LLM agent rollback restart checkpoint progress prediction recovery paper
6. "self-repair" "resampling" "Silver Bullet"
7. LLM code "repair" "restart" adaptive inference budget
8. "Re-FORC" adaptive reward prediction
9. "CodeRescue" arxiv
10. "Re-FORC" "Adaptive"
11. "Is Self-Repair a Silver Bullet" arxiv
12. "Debug or Regenerate" PATSSEL arxiv
13. LLM code repair "continue" "restart" "history" paper
14. LLM code repair "regenerate" "predict" strategy selection
15. LLM agent recovery checkpoint rollback "policy" "budget"
16. "GraphAHA" code generation
17. LLM "adaptive" "repair" "resample" code budget
18. LLM "restart" "progress" "prediction" coding
19. "CodeRescue" "AgentRewind" recovery
20. "VRL-Bench" memory recovery
21. "LLM" "repair" "resampling" "adaptive" site:openreview.net
22. "LLM" "restart" "history" site:aclanthology.org
23. "code generation" "repair" "Thompson" search
24. "Self-Repair" "Silver Bullet" 2306.09896
25. "Debug or Regenerate" "arxiv"
26. "Fail-Fast, Restart-Smart" code github
27. "Measuring and mitigating debugging effectiveness decay" authors
28. "Real-Time Detection and Repair of LLM Agent Failures" arxiv
29. "S* Scaling Test-Time Compute" code generation
30. "RethinkMCTS" code generation
31. "Self-Repair" "Reflexion" "resampling" code study
32. "LATS" language agent tree search code generation
33. "LLM" "optimal" "restart" reasoning computation
34. "code generation" "adaptive" "repair" "bandit"
35. "LLM agents" "model switching" trajectory routing paper
36. "Thinking Traps in Long Chain-of-Thought"
37. "AB-MCTS" "arxiv"
38. "Session-Aware Agentic Routing" model
39. "LLM" "predicting restart benefits"
40. "restart" "algorithm selection" "dynamic" runtime prediction Luby
41. LLM "repair" "restart" "counterfactual" "history"
42. LLM "patch" "reuse" "predict" recovery repair
43. "Luby" "optimal speedup" restart 1993
44. "adaptive inference-time compute" "Manvi" restart
45. "DARS" "Dynamic Action Re-Sampling" arxiv
46. "repair" "resample" "policy" "LLM" cost
47. "LLM" "history" "continue" "restart" repair -site:reddit.com -site:medium.com
48. "code repair" "treatment" "counterfactual"
49. "code repair" "history" "value" "restart" paper
50. "repair" "regeneration" "router" LLM
51. "agent" "partial progress" "restart" "predict"
52. "LLM" "rollback" "causal" recovery

</details>

## Historical focused check — 2026-10-22


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
