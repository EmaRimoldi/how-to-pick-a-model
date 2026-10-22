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
order jobs. Four bounded network workers, serialized isolated evaluation, and
randomized submission within each checkpoint. The two models are a practical
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
  Bonferroni simultaneous 99.375% intervals for this family of eight contrasts.
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
