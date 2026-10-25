# Prospective MBPP+ replication

## Question and claim boundary

After a naturally failed program, does the artifact add useful information
beyond public test feedback, both for the next solver and for choosing its next
action? The earlier HumanEval+ transfer result did not establish reliable benefit
prediction or a gain over a strong static recovery rule. Its 25 evaluation
failures are too few to justify a general controller claim.

This is an external-benchmark replication with frozen source-trained predictors,
not a search for a significant result. Post-failure routing, code/feedback
factorials and placebo controls already have close precedents in
[CodeRescue](https://arxiv.org/html/2607.19338v1) and
[Falsification, Not Exposure](https://arxiv.org/abs/2606.31511). We do not claim
those ideas or a new learning algorithm. CodeRescue's administrative withdrawal
does not remove its disclosed ideas from prior art. This experiment is not a
reproduction of either paper's trained system.

## Population, reference audit and selection

Pin EvalPlus 0.3.1, MBPP+ v0.2.0, MD5
`ee43ecabebf20deef4bb776a405ac5b1` (378 tasks). Before model calls, run every
canonical reference through the exact public-base and full base+Plus verifier.
Save all results; exclude only references that fail this compatibility check,
recording explicit IDs and a checksum in the config. Preserve official MBPP
special-oracle semantics, including set equality and output-not-None. Use
EvalPlus's task-specific input serialization/deserialization, including complex
inputs. Do not patch the benchmark to improve model results.

Dataset references: [MBPP](https://arxiv.org/abs/2108.07732),
[EvalPlus](https://arxiv.org/abs/2305.01210), and the pinned
[checker implementation](https://github.com/evalplus/evalplus/blob/v0.3.1/evalplus/eval/__init__.py).
Reference infrastructure-limit failures are compatibility exclusions too: their
exact recorded status remains visible instead of being presented as model errors.

Pre-call reference census: all 378 base checks pass; 377 full-suite checks pass.
`Mbpp/599` passes base but its official sum-of-range implementation exceeds the
isolated verifier's limit on the additional inputs. It is the only exclusion.
The complete [reference journal](data/reference-audit.jsonl) and
[frozen config](configs/replication.json) preserve this decision before model
responses. The [source policy](configs/frozen-policy.json) is also fixed in Git.
An additional [public-spec check](data/public-spec-audit.json), completed before
recovery responses, finds all 378 prompt assertions compatible with their
references when `math` is supplied by the assertion harness. This does not prove
that the references capture every English specification correctly. It changes
no primary exclusions or selected task.

Sort eligible task IDs numerically, shuffle once with seed 20261025, then generate
one initial program per task in that order. Use Ministral 3B 2512, Mistral's
pinned endpoint, temperature 0.6, 1536 output tokens, user-only JSON solve
instruction, no fallback or sampler seed. This keeps the producer identical to
the observed HumanEval+ evaluation, although the combined training set contains
both Gemma and Ministral failures. Provider precision is reported as unknown.

Only public-base failure triggers recovery. Include empty, malformed, syntax,
ordinary wrong-answer and provider-error failures; do not filter for promising
artifacts or by hidden Plus outcomes. The first **at most 96** failures in the
frozen shuffled order form the selected recovery sample. All initial outcomes,
including visible false positives, remain recorded. No replacing difficult or
unhelpful tasks. All-three-malformed initial smoke calls stop for inspection.

Base test inputs and acceptable reference outputs are explicitly public in this
regime. Plus remains evaluation-only, absent from the public-verifier subprocess
payload and from model requests. The public channel gives at most three failing
input/output examples, the failed fraction and verdict. Full success requires
base AND Plus. Stop a replay on a public pass, even when Plus later shows it was
a false positive. This is oracle-relative benchmark success, not deployment
correctness or a contamination-free evaluation of new programming skills.

## Matched bank

On each selected failure collect **three draws** for every combination of:

- Qwen3.5 9B and 27B, pinned `siliconflow/fp8`;
- fresh task, failed code alone, public feedback alone, code+feedback, and a
  distractor code+feedback package from a different HumanEval+ training failure.

The same solve instruction, 1536-output-token ceiling and temperature 0.6 apply.
Reasoning and fallbacks are disabled. No sampler seed is sent; local seeds only
order jobs. Four bounded network workers, two isolated verifier workers, and
randomized submission within each checkpoint. Initial-prefix collection and
reference compatibility checks are serial; recovery verification uses two
workers to reduce wall time. This resource choice is fixed before model calls;
each candidate retains the same subprocess CPU/wall limits and separate
public/private payloads. The two models are a practical
capacity comparison, not an identified causal effect of parameter count.

Donor choice is deterministic: numerically parse the MBPP task ID and take its
remainder modulo the lexically sorted 51 training checkpoints. Resize donor code
and feedback independently to the relevant field's **character** length. This
preserves the earlier control, but is not token matching: publish token
distributions and do not attribute differences entirely to semantic relevance.
The distractor is never a selectable policy action.

Admit a whole 30-request checkpoint block only when the remaining collection
budget covers the sum of its worst-case reservations. Do not inspect its branch
outcomes before this gate. A budget stop leaves the selected remainder explicitly
unmeasured, never silently removed. Transport uncertainty stops new admissions;
keep all already admitted observations and full unknown reservations. There is
no automatic retry, resume, provider substitution or key rotation.

## Source training and frozen comparison

Use all **51** failed states from the prior audited HumanEval+ validation bank:
26 former development and 25 former evaluation states, two draws per action.
Those former evaluation scores are now development evidence only. Verify the
tracked source checksums. Fit before any MBPP response; no MBPP fitting,
hyperparameter selection, feature search or threshold adjustment.

Keep the earlier Beta(1,1) per-action priors, ridge penalty 10, normalization from
training only, and probability clipping [0.01,0.99]. Four predictor views:

1. Global action priors.
2. Task: log prompt character and line lengths.
3. Feedback: task features plus base failure fraction and public
   NameError/SyntaxError/TypeError/timeout/format indicators.
4. State: feedback features plus log code length, log AST size and syntax-valid
   indicator. This adds exactly three artifact features to the feedback view.

These are deliberately small diagnostic baselines, not a claim that structural
features exhaust semantic artifact value. Feedback and state see the same
verifier information. Save all weights, costs, source hashes and action
predictions before the first MBPP target-model response.

At a fixed verified-solution value $0.01 and task ceilings $0.003/$0.01/$0.02,
choose the admissible action maximizing predicted value minus source mean API
cost; decline if nonpositive. Include producer cost. Before every draw enforce
the worst-case input/output reservation, not the future observed bill. At most
**two** draws of the same chosen action from the original checkpoint; no update
from the first child. Static selection uses complete two-draw recovery replay
on the 51 training failures separately for each budget. Thus its finite horizon
matches the primary policy comparison; no retrospective test-best rule is
promoted as a baseline. Also report all eight fixed actions transparently.

## Analysis fixed before outcomes

**Primary:** state minus feedback-only policy mean net utility
(`0.01 * full_success - total_API_dollars`) on selected failed checkpoints at
the $0.01 whole-task ceiling, using draws 0 and 1. Cluster-bootstrap tasks,
10,000 resamples, seed 20261025, two-sided 95% percentile interval. Report
success and cost differences separately. An interval spanning zero is
inconclusive, not equivalence. No stopping when significance appears.

This is conditional recovery after a failed prefix. Do not claim a whole-task
gain over always-9B/27B across the full benchmark: passing-prefix direct controls
are not collected. Fresh branches do support conditional direct-model controls
without producer charges, clearly labelled as such.

Prespecified secondary diagnostics:

- Joint state policy versus the source-selected static rule, the task/global
  policies, and state model-only routing (always code+feedback). Keep model
  routing distinct from deciding which context to preserve.
- For each model: artifact-fresh, both-fresh, both-feedback and both-distractor
  task-mean success differences over all three draws. Report ordinary 95% and
  Bonferroni simultaneous 99.583% intervals for the family of twelve contrasts
  (eight within-model contrasts plus the four corresponding small-minus-large
  differences in context effect).
  Do not selectively promote an unadjusted secondary interval.
- All rates, input/output tokens, actual API cost, format/provider failures,
  public false positives, missing cells and source-to-target feature shifts.
- Brier scores and mean squared errors of predicted both-feedback and
  both-fresh differences. Paired state-feedback loss differences use task
  bootstrap. Observed three-draw effects are noisy, not per-task ground truth.
- Exploratory variance of latent context benefit: cross-products of independent
  draw differences estimate between-task variation without treating sampling
  noise as signal. Subtract an unbiased cross-task estimate of squared mean.
  Report negative finite-sample estimates and intervals without clipping. This
  assumes conditionally independent provider draws; it is a diagnostic, not a
  new estimator or proof that effects are predictable.
- Sensitivity replay on rotations (1,2) and (2,0), retaining the original
  primary (0,1). Never average a favorable rotation into the primary.

If the selected bank is incomplete, report completion and worst-case bounds
over every selected state. Complete-case intervals are descriptive and cannot
be described as a completed confirmatory test. Fewer failures reduce precision;
do not generate extra task variants or switch producers to chase power.

With 96 independent failed tasks, three draws and independent Bernoulli rates
near 0.7, a homogeneous-effect approximation gives about 7.5 pp 95% half-width
for a paired context contrast and about 11 pp detectable difference at 80%
power. Task heterogeneity/dependence can make this worse, and fewer than 96
failures may occur. This is not powered to establish equivalence at a few pp,
nor does a larger response count replace independent task clusters.

## Spend and publication

The approved cumulative cap is **$2**. Earlier known charges plus all unresolved
reservations total **$0.5149634**. This replication's cap is **$1.48**; even full
use leaves the campaign upper bound at $1.9949634. The six earlier unresolved
admissions remain reserved; do not spend their headroom twice. Keep settlement
receipts, reservation journal, model/provider snapshots and all observed outputs.
Never persist credentials or personal account balances.

The deliverable is an audited replication and a separate evidence-grounded paper
draft. A positive controller result, top-conference acceptance or broad software
engineering generalization is not promised. Report null and negative results,
prior-art overlap, benchmark contamination risk and the single-provider,
single-checkpoint limitation. Existing historical manuscripts remain separate.

Before any recovery response, the secondary contrast family was extended from
eight to twelve to test model-by-context interactions directly. A difference
between a significant small-model effect and a nonsignificant large-model effect
does not establish an interaction. All twelve therefore use the stricter
Bonferroni interval above. The primary remains unchanged; the pre-recovery
amendment and zero-target-response check are preserved in Git and the freeze log.

## Secondary semantic control, frozen before recovery outcomes

Addendum fixed after initial-producer collection began (123 prefix responses,
zero target/recovery responses at the engineering check), before any recovery
outcome. The primary, bank, learned weights, task selection and budgets above
remain unchanged. This control addresses the weakness of prompt-length-only
features; it is not selected after inspecting recovery wins/losses.

Freeze `transfer_forecast.py` now. If budget remains after the primary collection,
collect Qwen 9B forecasts with three views: task-only, public-feedback-only, and
full state (feedback plus failed program). All share the same eight source priors,
source mean costs, solve-probability instruction and target-model identities.
No recovery response, evaluation label or Plus datum enters the forecaster.
Record all malformed forecasts with the existing 0.5 fallback and their full fee.
Four network workers, same pinned small-model endpoint/parameters, no retries.

To avoid overlapping budget allowances, this separate run begins only after
primary collection ends. Its ceiling is min($0.08, $2 minus every prior known
charge and unresolved reservation). Weights/prompts are fixed before recovery
outcomes; **forecast responses themselves are collected after them**, so describe
this as a prespecified outcome-blind semantic control, not a physically prospective
deployment trial. The primary local predictions remain physically prospective.

Secondary analysis: the same Brier and benefit-MSE diagnostics, plus two-draw
budgeted replay with each forecast's measured fee charged before the chosen
action. Admission first reserves the worst-case forecaster call and then the
chosen solver call. Compare full-state versus feedback-only, task-only and
the strong static rule, with task-bootstrap intervals. All are secondary,
without replacing the primary or a multiple-testing win claim. Missing forecasts
are explicit; do not substitute free forecasts or silently drop expensive failures.

## Explicit late-prefix transport continuation, before any recovery response

Initial collection stopped after **347 observed prefixes** and 120 public
failures. Admission 348, `Mbpp/74`, returned no preserved response identity
(`URLError`); its **entire $0.0026112 reservation stays held**, alongside
$0.0061082 of observed prefix charges. No recovery response existed at this stop.
The original run journal remains immutable.

The first 96 failures were already observed before admission 348. Therefore this
late missing prefix cannot change the selected recovery cohort, regardless of
its unobserved outcome. An explicit `--continue-prefix-from` imports every known
response/evaluation and every budget event into a fresh directory, preserving
call IDs and the unknown reservation. It **never reissues** the 347 observed
prefixes or the unknown `Mbpp/74` request. It completes only the 29 unadmitted
prefix tasks, then collects the unchanged first 96 matched recovery blocks.
The same $1.48 run limit includes all imported charges and reservations.

The original `manifest.json` remains the frozen experimental identity so that
source weights, task order and semantic-control identity stay unchanged.
`prefix-continuation.json` separately records the new collector Git/source hash,
source-file hashes, exact imported counts, censored identity and proof that the
selected IDs are unchanged. A separate sanitized preflight records current
endpoint availability. Evaluator, policy, prompt and billing-transport helpers
must match the original hashes. No provider, model, sampler or hypothesis changes.

Report **376 observed prefixes plus one censored prefix among 377 eligible
tasks**, rather than a complete benchmark census or a zero-cost/model-failure
imputation. Whole-benchmark initial success has a one-task uncertainty bound.
The selected 96-state primary bank remains fully defined and unaffected by this
late censoring; missing recovery cells would still make its inference incomplete.

## Additional constant-escalation diagnostic

Implemented after recovery collection began, before treatment statistics were
computed: a fixed 9B-fresh attempt followed, only after public failure, by a
27B-fresh attempt. This uses recorded independent draws from the original
checkpoint; it does not feed a new child's code or feedback to the second model.
Charge the prefix and each admitted receipt, stop on public passes including
false positives, and use the same advance reservations and two-attempt cap.
It adds no inference calls and performs no selection on MBPP scores. Report it
as an additional diagnostic, distinct from the frozen primary and the original
prespecified comparisons. Do not promote a favorable comparison with it to a
new confirmatory result.

## Human-authorized continuation after recovery transport censoring

The recovery segment stopped after 47 complete checkpoints and three additional
observed solver responses. Admission 1791 (`Mbpp/426`, checkpoint 130, 27B code-only,
draw 2) has no preserved response identity. Its full $0.009216 reservation remains
held, in addition to the earlier $0.0026112 prefix reservation. The stopped
segment contains 1,789 observed responses, $0.40929355 of known charges and
$0.0118272 of unresolved reservations. Including the unchanged prior $0.5149634,
the campaign upper bound at this boundary is $0.93608415.

After a user-requested 22-state descriptive snapshot and a descriptive audit of
the stopped 47-state bank, the human explicitly authorized: **"Sì, continua solo
con i tentativi mai inviati"**. The
[authorization freeze](configs/recovery-continuation-freeze.json) records the
stopped-file hashes, collector hash and exact 1,466 never-admitted cells. This is
an explicit exception to the automatic-resume prohibition, not a retry policy.
No source or target fitting, task selection, prompt, model, provider, precision,
sampler, verifier, primary estimand or declared dollar limit changes.

The new collector imports every known observation and budget event once into a
fresh journal. It preserves the original manifest and prediction bytes, excludes
every observed or uncertain cell from requests, and passes the same conservative
whole-block budget gate before new admissions. The unchanged $1.48 primary cap
includes all imports and pending reservations. A new transport failure stops new
admissions again. The stopped source remains immutable; separate recovery
lineage records hashes and counts of all imported journal prefixes.

The one censored cell is a third draw. It remains missing permanently, even if
the rest of the planned bank is collected. Do not relabel the 30-cell bank as
complete. Under the original completeness rule, complete-case intervals remain
**descriptive**, and all 96 selected states remain represented in missing-state
bounds. Report the observed partial audit and this continuation timing; do not
silently replace the primary or promote a favorable secondary contrast.

A later transport failure stopped the authorized continuation at 80 complete
checkpoints and 2,445 observed recovery responses. Admission 2817 (`Mbpp/84`,
checkpoint 237, 9B fresh, draw 0) remains unobserved with its full $0.002688
reservation. The cumulative primary charges are $0.67915665, unknown reservations
$0.0145152, and campaign upper bound $1.20863525. The remaining 433 cells are a
strict subset of the original 1,466 explicitly authorized cells. Their
[child freeze](configs/recovery-continuation-segment2-freeze.json) preserves that
root authorization and all stopped-file hashes before further requests. No new
permission, budget, hypothesis or response replacement is introduced. Each later
segment archives previous lineage metadata, preflight and stop summaries byte
for byte, with a checked parent index. Two selected checkpoints now contain
censored solver cells, so at most 94/96 checkpoints can have all 30 observations.
Complete-case intervals remain descriptive; all 96 selected states stay in bounds.

## Final collection census, 2026-10-22

All authorized primary cells are now accounted for: 2,878 observed recovery
responses and the two permanently censored cells, with 94/96 complete selected
states. There are 376 observed prefixes and one censored prefix. The secondary
control then collected all 288 forecasts, all valid, without new uncertainty.
No further model requests are required for this study.

Primary known charges are $0.83799455 and unresolved reservations $0.0145152.
The semantic control adds $0.0285302. Including the earlier $0.5149634 campaign
upper amount, known charges plus every reservation total $1.39600335 under the
unchanged $2 ceiling. This census records the completed authorized collection;
it does not amend hypotheses or restore confirmatory completeness. Read the
[curated evidence](results/replication-20261022/README.md) for reproduction.
