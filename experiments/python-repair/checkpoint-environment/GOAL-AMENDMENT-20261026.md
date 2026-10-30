# Research goal amendment: acquire evidence before another repair?

**Latest step (2026-10-30 UTC):** the user requested proceeding after one minimal
availability check succeeded on the same research key/model/provider. The
[new separate spectrum screen](SPECTRUM-PROTOCOL.md) compares complete public
coverage rankings against concurrent feedback-only controls at eight generated
failed checkpoints, three draws per arm. It declares a $0.36 allocation inside
the existing $0.60 cap, carrying $0.22775259 including fourteen prior reserves.
This is an information-value development screen, not selector training or an
equal-total-resource policy claim. No new repair results are available yet.
The earlier dashboard discrepancy is explained by distinct accounts; the
historical 429 cause and uncertain charges remain unresolved.

**Previous verified status (2026-10-29 UTC):** the user resumed the unchanged goal.
The [frozen-region model study](results/frozen-region-stopped-20261027/README.md)
remains closed after HTTP 429 with 11/32 responses and an inconclusive gate.
The API can retrieve one known paid receipt, while the dashboard showed no
requests; the cause of the 429 and fourteen uncertain reserves remain unresolved.
Support submission is user-managed. Cumulative commitment remains
$0.22774335 / $0.60; no new allocation or model request was made.

An [offline public-coverage audit](PUBLIC-SPECTRA-AUDIT.md) now provides a concrete
alternative diagnostic to investigate. On the eight previously exposed original
bugs, public-test coverage yields different suspiciousness scores among
failing-executed lines in seven cases and a complete tie in one. This is
feasibility, not localization accuracy or improved repair. All 48 public
observations agree across stored, fresh ordinary and covered execution. The
diagnostic used no reference fix or private evaluator. It does not replace the
required experiment on model-generated failed checkpoints, the repeatability
screen or untouched policy evaluation. No selector is trained; all historical
gates and closed collections are preserved. Historical progression is retained below.

A subsequent [generated-failure feasibility audit](results/generated-spectra-20261029/REPORT.md)
now covers all eight public failures among twelve retained historical Gemma 27B
JSON outputs. Seven yield non-flat line scores; one stays tied. All 48 public
observations agree, with no private outcome used and no new model calls. This
extends feasibility to actual failed attempts, not efficacy: seven bugs belong
to one project, and the matched repair experiment remains necessary.


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


## Operative milestone renewed by the user

On 2026-10-26 the user instructed “Procedi, set the new goal.” The immediate
measurable deliverable is now the [matched Qwen information calibration](QWEN-INFORMATION-PROTOCOL.md):
64 fresh requests, eight failed checkpoints, four draws per arm, focused public
feedback versus the same feedback plus a bounded public execution trace. Keep
all twelve source candidates and report full repairs, false acceptance,
regressions and all costs. The prospective engineering gate and incomplete-data
rules are fixed in that protocol before collection.

The final goal remains a prospective, cost-aware diagnostic-acquisition selector
that improves on the best fixed policy on untouched bugs/projects. A completed
calibration is only a milestone; an unfavorable result is retained and prevents
unsupported selector training. Equal-total-resource benefit and generalization
require subsequent separately declared studies.

At the initial replacement attempt the app goal manager reported the old objective
as blocked and rejected a replacement while it was unfinished. The new operative scope is
recorded here and in the research state; the old objective has not been falsely
marked complete. The user has authorized proceeding, and no active collector is
being resumed. The new allocation is $0.47 within the retained $0.60 total, with
$0.06942739 carried once including all eight old uncertain reservations.


## Terminal status and managed goal update

The user subsequently set the new objective manually; `get_goal` confirms it
active. The earlier rejected replacement is history, not a current blocker.
The full selector objective remains unfinished and must not be marked complete
at the end of a calibration or infrastructure milestone.

The [matched Qwen information study](results/information-qwen-stopped-20261026/README.md)
closed after a connection timeout: 18/64 responses, nine per arm, with 3 versus
2 full repairs. One unknown request retains its reservation and 45 were never
admitted. The frozen primary bounds are −68.75 to +75.00 percentage points;
mean/bootstrap remain null and the gate inconclusive. No selector training,
retry, resumption or successor is authorized by that protocol. Its cumulative
commitment is $0.08592275, including nine unresolved requests across studies.

This does not establish an ineffective intervention either. The immediate
research dependency is reliable collection of the planned comparison under a
separately reviewed prospective protocol; no favorable complete-case metric
can replace the missing evidence. The original benefit, equal-total-resource
policy comparison and untouched-bug evaluation remain required.


## Independent development extension: terminal status

The separately frozen [three-bug extension calibration](results/information-extension-stopped-20261026/README.md)
received 9/24 responses before its second `ConnectionResetError`, both localized
to reading response bodies. Two requests remain uncertain and thirteen were
never admitted. Four focused-feedback versus two trace-assisted full repairs
are observed; primary bounds remain −75 to +50 percentage points, mean/bootstrap
null and the gate inconclusive. All 18 saved evaluations reproduce independently.
The study is closed with no retry, resumption or successor; no selector is trained.

Cumulative commitment is now $0.10576463 / $0.60, including eleven unresolved
requests across closed studies. The collector followed its prospective bounded
uncertainty rule, but that rule did not establish reliable collection. The cause
of the body resets remains unestablished. Technical validation of transport is
the immediate dependency before another scientific bank; an incomplete bank is
not evidence for choosing a preferred diagnostic strategy. The larger goal and
its requirements for repeatable benefit, equal total resources and untouched
bugs remain unchanged and active.


## Complete independent-cell calibration: benefit screen failed

The [separately frozen independent-cell bank](results/information-independent-20261026/README.md)
completed all 64 requests without a new transport error or missing outcome.
Focused feedback produced 12/32 full repairs, versus 8/32 with a bounded public
trace; primary difference −12.5 pp, descriptive 95% bug-bootstrap interval
[−31.25, +3.125] pp. The prespecified screen fails in both draw halves. These
are eight already exposed bugs, not a held-out evaluation or proof of population
harm. No selector is trained. The next action is a labeled post hoc diagnosis
of the information intervention, followed by a separate prospective test only
if the diagnosis supports a concrete revision. Equal-total-budget benefit and
untouched-bug validation remain necessary for the original active goal.

This study adds $0.03910528 known spending and no uncertainty; cumulative
commitment is $0.16495655 / $0.60 including thirteen historical reserves. All
collectors are closed. Prior studies, gates, sources and manuscripts remain
intact, with no pooling, retries or replacement of missing cells.


## Post hoc diagnosis and revised acquisition preparation

The [complete-bank audit](results/information-independent-posthoc-20261026/README.md)
retains all twelve source candidates and all 64 responses. Seven of eight traces
lose no events; six contain value omissions. Thirty-nine responses correct at
least one initial public failure, but twenty fully repair, and four pass public
tests while failing evaluator checks. These overlapping development observations
separate local progress from complete repair; they do not establish a cause.
The primary 12-versus-8 result and failed benefit screen remain unchanged.

The next candidate intervention is a [bounded failing/passing public execution
contrast](CONTRASTIVE-DIAGNOSTIC-DESIGN.md), with a same-representation single-trace
control and focused-feedback baseline. The implementation uses no hidden oracle
or generated expected answer. [Offline qualification](results/contrastive-preparation-20261026/README.md)
checks both variants on all eight triggered sources and preserves four untriggered
sources; no model calls were made. This does not demonstrate benefit or permit
selector fitting. A separately frozen and allocated development comparison is
required before any new collection; no paid allocation exists for it yet.

The literature check adds direct precedents in contrastive tests and execution
cost allocation. Neither constructing a contrast nor deciding whether execution
is worth its cost is, by itself, a novelty claim. The full goal still requires
repeatable useful acquisition, enforced total-resource policy comparisons and
untouched grouped evaluation against the best fixed strategy.
