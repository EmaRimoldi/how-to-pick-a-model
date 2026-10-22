# Frozen task-held-out recovery validation

Protocol frozen before model calls. This iteration addresses the discovery
study's limited failure diversity and its lack of an evaluated action selector.

## Population and split

HumanEval+ v0.1.10 / EvalPlus 0.3.1, MD5
`fe585eb4df8c88d844eeb463ea4d0302`. The 54 previously studied tasks are development
only. Numerically sort the 90 tasks outside those 54, the 19 original reserve
tasks and HumanEval/47; shuffle with seed 20261024. Add the first 30 to development
and use the remaining 60 for untouched evaluation, then remove HumanEval/32
from whichever split contains it. Explicit IDs and their checksum are frozen
in `configs/validation-split.json` and `configs/validation.json`.

Reference compatibility was checked before model calls. Task 47 has a contradictory
public median example. Task 32 fails even with its reference under the pinned
EvalPlus checker: the special `find_zero` success path skips progress/detail
updates, causing the check to report failure. Both are excluded; the dataset and
installed package are not silently patched. The original 19 reserve tasks remain
outside both development and evaluation.

## Public verifier and real failed work

The base inputs and their acceptable reference outputs are explicitly public
feedback in this regime. Plus inputs/results remain evaluation-only. This is a
different feedback regime from the earlier doctest-only discovery experiment;
do not pool their rates as if protocols were identical.

Generate one Gemma 3 4B IT candidate per task, with a user-only solve instruction,
JSON solution, temperature 0.6, 1536 output tokens and no reasoning parameter.
Endpoint: `deepinfra/bf16`, price ceilings $0.05/$0.10 per million input/output
tokens. Use a smaller producer to collect natural errors rather than injecting
bugs. This is not a causal parameter-size comparison: producer/consumer families,
training and some precisions differ. Keep passing prefixes and format failures.
Only public-base failure triggers recovery; never select by Plus failure.

The first three development calls are a technical smoke check and remain in the
dataset. If all three are malformed, stop for inspection, preserving every
charge. Stop fitting if fewer than 20 independent development tasks fail; that
coverage gate is not a power calculation or a publication-quality guarantee.

## Matched recovery bank

For every failed checkpoint, Qwen3.5 9B and 27B each receive two independent draws
in five conditions: fresh task, code only, feedback only, both, and a distractor.
The Qwen endpoints remain `siliconflow/fp8`, price ceilings $0.10/$0.15 and
$0.25/$2.00 per million input/output tokens. Reasoning and fallbacks are disabled;
no provider sampler seed is sent. Use the same instruction in every condition.

The distractor uses a real different development task's failed code and public
feedback, selected deterministically. Truncate/pad each field to match the
relevant package's character length. **This is character matched, not token
matched**: report provider input-token distributions, including discrepancies.
Held-out distractors use development donors only. No Plus result enters any
context. Irrelevant contexts are diagnostic controls, not selectable actions.

Shuffle job submission with a fixed local seed; use four bounded network workers
with locked reservations/journal writes and serial candidate evaluation. Persist
actual calls/order. Unknown billing stops further admissions, keeps reservations
and collects already admitted responses; no automatic retries or journal resume.

## Frozen forecasts and policies

Complete development collection first. Fit only on complete matched development
states, with one parent per task. Fixed smoothing Beta(1,1), ridge penalty 10 and
probability clipping [0.01,0.99]; no hyperparameter or feature search:

- Global per-model/condition success and cost estimates.
- Task ridge: prompt character/line lengths.
- State ridge: those task features plus code size, AST size, syntax validity,
  base failure fraction, NameError/SyntaxError/TypeError/timeout/format indicators.

Save weights, training IDs and training-branch hash **before any held-out model
call**. The value of a fully verified solution is fixed at $0.01. Select the
admissible action maximizing estimated value minus development mean API cost;
decline if all estimated net values are nonpositive.

On held-out failures, also collect task-only and state API forecasts using Qwen
9B. Both get the same development priors/costs and know that an earlier attempt
failed. Save them and frozen local predictions before recovery calls. Count
malformed forecasts with a declared 0.5 fallback. No fitting on evaluation data.

## Evaluation and primary comparison

Whole-task dollar budgets: $0.003, $0.01 and $0.02. Each policy may sample at most
two independent draws of its selected fixed action from the original checkpoint;
it does not update its state with the first child output. Stop on **public-base**
success, including false positives, not evaluation success. Admission uses the
declared worst-case input/output price bound before a draw, never its future
actual bill. Full success requires base AND Plus. Charge the prefix to recovery
policies and a forecast fee to API policies; local CPU time is reported separately.

Direct always-9B and always-27B baselines cover every held-out task with the same
fresh prompt and two-draw limit, without a producer-prefix charge. For a failed
prefix the observed fresh draws are identical direct-model controls and can be
reused; passing prefixes get additional direct controls. This finite two-draw
comparison is not a claim about unlimited retry strategies.

**Primary:** frozen state-ridge policy minus the development-selected best fixed
recovery action, net utility (0.01 * verified success minus API dollars) at the
$0.01 whole-task budget. Bootstrap held-out task clusters, 4000 resamples, seed
20261024, and report the 95% interval. Report success and costs separately too.
Task-ridge, global, API policies, other budgets and per-condition contrasts are
secondary exploratory comparisons; no multiple-testing significance claim.

A stricter secondary static comparator is also specified before evaluation:
choose the fixed action with the best **complete two-draw development replay**
utility separately at each budget, including prefix charges and stopping. This
tests sensitivity to the collector's original per-draw-prior fixed selection.
Both static choices use development only; neither is chosen from held-out scores.
The original primary comparison remains unchanged.

Secondary ablations separate generic model routing from context selection:
state-model-only chooses the next model while always supplying code+feedback;
state-context-small and state-context-large choose the context condition while
fixing the next model. They use the same frozen probabilities, value/cost rule,
admission caps and observed draws. Joint selection gains alone must not be
attributed to deciding what work to preserve without checking these controls.

Also report conditional recovery rates, false positives, censoring/incomplete
cells, abstentions, predictor Brier scores, errors on the **predicted difference**
between both-versus-fresh and artifact-versus-fresh, and forecasting overhead.
Differences estimated from two draws are noisy observed effects, not ground-truth
individual treatment effects. Do not interpret lower Brier as better decisions.

## Budget, provenance and deliverables

The approved cumulative ceiling remains **$2**. Prior committed discovery spend:
$0.0230224; this run is capped at **$1.97**, leaving additional headroom. Record
any engineering stop and debit both charges and unresolved reservations before
any explicit restart. Verifier/reference setup and wall time are not converted
to fabricated dollar charges. No credentials or account balances in curated data.

```bash
uv sync --dev --extra continuation-pilot --frozen
uv run python scripts/run_recovery_validation.py \
  --config experiments/humaneval-plus/context-value/configs/validation.json \
  --output runs/recovery-validation-plan
```

Planning makes no model calls. Authorized live collection uses a fresh output
directory and adds `--live --budget-usd 1.97 --key-stdin`.

### Transport correction before evaluation

The first development collection stopped after 151 requests because one explicit
empty provider error had no usage receipt. Its generation lookup returned 404.
OpenRouter's [zero-completion insurance](https://openrouter.ai/blog/announcements/never-pay-for-empty-ai-responses-again/)
and [pricing policy](https://openrouter.ai/pricing) specify zero model-token charge
for error responses; an authenticated aggregate-credit comparison matched all
other settled receipts to numerical precision. Record that draw as a failed
observation with a **policy-backed zero**, preserving the raw missing usage and
the reconciliation, rather than pretending it supplied a measured token receipt.

An explicit `--import-run` creates a fresh journal, imports every known response
and charge, verifies the unchanged evaluator and config, and reuses each job at
most once. Existing observations and the failed provider response are not
resampled. Only jobs without a prior response are generated. Imported inference
costs remain part of the same $1.97 run ceiling, not a new allowance. Unknown
non-error billing and requests lacking response identity still stop/refuse import.
This transport correction precedes policy fitting and all held-out calls; task
IDs, hypotheses, features, penalties and budgets are unchanged.

Produce an auditable report, figures, and a blog draft that includes negative
findings. A paper claim additionally needs a broader novelty review and stronger
replication; collecting data until a favorable result appears is not the plan.

Related primary sources: [Re-FORC](https://arxiv.org/html/2511.02130v2),
[AI Functions economics](https://github.com/strands-labs/ai-functions/blob/8f1485c2b685c83560bd91a0569cdf3af3176e75/docs/economics.md),
[DDBench](https://arxiv.org/abs/2608.14863), and
[ContextBench](https://arxiv.org/abs/2602.05892). Context usefulness and misleading
debugging context are already studied. This experiment targets forecasting and
budgeted selection among measured recovery actions; it makes no priority claim.
Dataset licensing remains covered by the upstream notices in the pilot bundle.
