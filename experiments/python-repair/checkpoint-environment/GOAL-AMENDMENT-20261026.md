# Research goal amendment: acquire evidence before another repair?

Status: user-directed amendment after the closed 4B/12B/27B development studies.
The user asked to redefine the goal from the observed failures and the literature,
then proceed. This supersedes the immediate continue/restart-selector milestone;
it does not rewrite any historical gate, task, outcome or budget. No selector has
been trained. The larger research goal remains unfinished.

## Diagnosis supported by our data

The [three-bank comparison](results/capability-comparison-20261026/README.md)
shows usable artifacts rising from 16 to 31 to 34 of 36, while complete
public-plus-evaluator successes rise only from 1 to 2 to 3. The 27B successes
cover two distinct bugs. Output formatting is no longer the dominant observed
failure at 27B. This does not isolate model size: precision, seeds, training
exposure and collection times differ.

The 27B bank has 26/36 outputs failing public tests and 7/10 public passes failing
evaluator tests. The latter seven concern only three bugs: five outputs violate
explicit preservation requirements; two expose ambiguity in our timestamp
specification. See the [post hoc case audit](results/diagnostic-audit-20261026/README.md).
These are correlated development observations, not seven independent defects.
The original buggy artifacts already passed 77.5% of public cases on average;
27B reaches 78.1%. A high per-test score is therefore insufficient evidence of
repair. Keep complete-task success and regressions as separate outcomes.

The working diagnosis is **limited effective repair information/capacity plus
incomplete acceptance tests**, with one identified specification ambiguity.
These data cannot distinguish weak localization from inability to implement a
known fix. They do not establish that more information will help. A selector
cannot create successful alternatives that the solver never generates.

## What the literature changes

Primary sources inspected on 2026-10-26; reported gains are not our replications.
This is a targeted extension of the [prior review](../../../docs/recovery-related-work.md),
not a proof that no other relevant paper exists.

| Source | Consequence for our experiment |
| --- | --- |
| [Olausson et al., ICLR 2024](https://arxiv.org/abs/2306.09896) | Cost-accounted self-repair gains vary; stronger feedback can improve them. Separate feedback quality from solver capacity and charge every attempt. |
| [Maniple / The Fact Selection Problem, ICSE 2025](https://discovery.ucl.ac.uk/id/eprint/10214057/) | Bug-specific fact selection already exists on BugsInPy. More facts need not help. The [method text](https://arxiv.org/html/2404.05520) includes an angelic-values condition extracted from fixed programs; our deployable diagnostic must exclude reference-derived values. A static fact selector is a comparator, not our novelty claim. |
| [Chen et al., ACL 2025](https://aclanthology.org/2025.acl-long.881/) | Generated expected answers can introduce misleading feedback. Study observed intermediate execution states without inventing an oracle. |
| [Haque et al., KnowledgeNLP 2025](https://aclanthology.org/2025.knowledgenlp-1.17/) | Naively adding execution traces helps only two of six configurations; complexity matters. Bound trace size and retain negative effects. |
| [TraceRepair, ASE 2026 per author record](https://arxiv.org/abs/2604.02647) | Trace-guided diagnosis and repair are already proposed. Collecting a trace is not a new method by itself. |
| [DynaFix, v2 preprint](https://arxiv.org/html/2512.24635v2) | Iterative runtime feedback and bounded refinement/restart already include acquisition-overhead and token-cost measurements. Costed traces alone are not new. |
| [CT-Repair, July 2026 preprint](https://arxiv.org/html/2607.12605v1) | Queryable static/dynamic evidence and feedback-guided strategy allocation are prior art. Charge representation construction as well as subsequent queries. |
| [Calibrate-Then-Act, v3 preprint](https://arxiv.org/html/2602.16699v3) | Prospective cost-aware acquisition already exists; include a calibrated pre-acquisition comparator. |
| [VeriHarness, July 2026 preprint](https://arxiv.org/html/2607.14167) | On TextWorld, actionable alternatives matter more than JSON versus prose. Its HumanEval scope check exposes the limit of invisible failures. Our existing feedback already includes public inputs, expected values and observations; reformatting them must be a separate control. |
| [S*, 2025](https://arxiv.org/html/2502.14382) and [PATSSEL, 2026](https://aclanthology.org/2026.findings-emnlp.2173/) | Execution-based candidate selection, iterative refinement and prospective routing have direct precedents. Include their relevant simplified baselines and all inference costs. |

## Revised objective and possible contribution

**Determine when a failed coding agent should acquire a bounded executable
diagnostic before spending its next generation attempt, rather than immediately
retrying or restarting. Build a prospective policy only if that acquisition has
reproducible value.**

The candidate contribution is a measured, cost-aware decision about acquiring
new information at a fixed failure checkpoint, using only information available
in deployment. It must beat both always-diagnose and never-diagnose policies on
untouched bugs under a common total resource envelope. This is a research target,
not a certified literature gap or a demonstrated new algorithm. A null finding
that acquisition has no useful headroom is a valid outcome.

The initial action set is small: direct repair, acquire one public execution
trace then repair, or stop when budget is exhausted. Restart from original code
remains a fixed comparator in the subsequent policy experiment; rollback and
model switching are deferred. Do not expand all actions before establishing one
useful intervention. The immediate engineering implementation is an offline
public-trace adapter, not an adaptive policy.

## Staged falsifiable plan

1. **Audit the measurement contract.** Preserve the twelve inspected development
   bugs and their historical scores. Record ambiguous specifications separately.
   Any clarification is a newly versioned development task. Never promote a
   viewed evaluator case into a supposedly unseen test or silently remove a bug.
2. **Establish a useful intervention.** On identical failed checkpoints, compare
   raw existing feedback, a focused rendering of exactly that information, and
   the same rendering plus bounded candidate execution traces. Use one pinned
   model/precision, one output contract and replicated draws. Compare full
   public-plus-evaluator success, regressions, false acceptance, dollars and
   local runtime. The first study is development diagnosis, not confirmation.
3. **Separate information from opportunity cost.** A one-call contrast tests
   information value, not an equal-budget policy advantage. If it is promising,
   run direct retry/restart and diagnostic-first policies under the same API cap
   and local-runtime cap. Charge the prefix, diagnostic prompt tokens, acquisition,
   selection, failed calls and unresolved reserves; report realized spending.
4. **Learn only after repeatable action headroom.** Before the trace is acquired,
   a selector may see code, public feedback, progress and remaining budget; it
   cannot see the future trace for free. Compare a static fact-selection router,
   a calibrated expected-value rule, fixed policies, and a two-candidate verifier
   baseline that pays for both. Calibrate only on development data and charge
   estimation/selection as part of deployment; include unreliable estimates
   in a separately declared robustness check.
   Sparse two-draw action differences are not sufficient training evidence.
5. **Freeze an untouched evaluation.** Group all variants/replicates of a bug,
   separate projects where feasible, declare a meaningful effect and powered
   sample before results. Use a paired bug-level primary contrast against the
   development-selected best fixed policy, with success and false acceptance
   jointly reported. No post hoc exclusion or favorable secondary substitution.

If the trace adds no reproducible benefit over same-information feedback, do not
fit a trace-acquisition selector. Investigate solver specialization or task
contract coverage under a separate protocol. If gains appear only on visible
tests, the intervention has not met the repair objective. A trace of a passing
public test cannot be assumed to reveal an untested requirement.

## Current action and limits

The [diagnostic adapter](DIAGNOSTIC-PREPARATION.md), frozen information study and
[terminal replay](results/information-stopped-20261026/README.md) are delivered.
After two HTTP 429 interruptions, 65 of 96 planned outcomes were received; all
65 are usable but none fully repairs a bug. Thirty-one cells remain unknown,
so the original screen is inconclusive. Do not convert this into a general null
effect or change the gate to permit training.

The post hoc edit audit sharpens the immediate diagnosis: 25 exact copies and
25 additional entrypoint-only syntax changes preserve the internal implementation
in many answers. Limited capacity, code preservation and ambiguous interpretation
of the repair instructions remain competing explanations. More trace information
has not yet supplied successful alternatives for a selector to choose from.

The [interface control](STAGNATION-CONTROL-DESIGN.md) subsequently changed two
non-oracle cues independently: the provenance comment and explicit permission to
edit helpers. Its [closed bank](results/interface-stopped-20261026/README.md)
contains 44 usable responses, eleven per condition, and no complete repair. An
HTTP 429 leaves 84 cells unknown and the gate inconclusive; the primary bounds
span −65.625 to +65.625 percentage points. Thus the observed failures have not
been resolved by either tested cue. This is not proof that instructions never
matter or that the model cannot repair these tasks under another setup.

A separately controlled [solver-compatibility positive control](SOLVER-PROTOCOL.md)
has now [completed all 32 Qwen3-Coder-Next/Parasail/BF16 draws](results/solver-qwen-20261026/README.md),
preserving the same tasks, original messages and verification contract. Ten
complete repairs span five bugs; three bugs have success in both draw halves,
passing the unchanged compatibility screen. All 62 saved evaluation records
reproduce independently. One public false acceptance, eleven public-score
regressions and six unusable responses remain in the report.

The next step is a separately frozen diagnostic-intervention calibration with
fresh matched control requests. The historical controls cannot serve as its
concurrent baseline. This result demonstrates practical repair compatibility,
not why Gemma differed or whether traces help. The final goal remains a deployable
acquisition policy that improves on the best fixed action on untouched bugs;
its benefit and novelty are still unproven. This development control is not
that policy or its held-out evaluation.

The independent [source-trigger audit](results/solver-qwen-20261026/trigger-coverage-audit.json)
also retains three evaluator failures among four unchanged public-pass sources,
including one known specification ambiguity. Under the frozen criterion, even
perfect recovery of every triggered failure would reach at most 9/12 accepted
source tasks if the public-pass artifacts stay unchanged. This conditional ceiling
is not an observed policy result. Recovery and acceptance coverage require
separate reporting; any verifier/specification revision needs a new version.

Accounting totals $0.06942739 including eight historical unresolved reserves,
under the existing $0.60 ceiling. All collectors are closed; no recursive
successor is enabled. The solver control spent $0.01816000 of its separately
declared $0.24 allocation and introduced no new uncertainty.
Every new collection needs a separately declared sublimit, reviewed clean source
freeze, exact requests, analysis and single-use launch claim. Historic uncertainties,
scores, manuscripts and failed gates remain preserved.

The managed goal tool cannot edit an active objective's text. This user-authorized
amendment and `runs/ACTIVE_RESEARCH_STATE.json` therefore record the operative
scope; the earlier objective must not be marked achieved merely to replace it.
