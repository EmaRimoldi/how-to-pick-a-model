# Prospective whole-program diagnostic pilot

Status: **numerical design, not yet a live collection freeze**. No model call is
enabled. The tested collector, executable analysis, exact source commit, runtime,
current provider metadata and single-use funded manifest must agree with this
document before launch. No new credit is requested or assigned by this draft.

## Question and scope

After one model-generated Python repair fails public tests, do truthful
test-to-line associations improve the next repair beyond showing the same covered
source excerpts without associations? The primary contrast is S minus N; S minus
F is the fixed feedback safety comparator. This is an information-value pilot,
not a trained selector, equal-total-resource policy test or confirmatory claim.

Use the eleven first-eligible pairs in the
[prospective source qualification](results/fixeval-source-qualification-20261030/README.md),
in its recorded order. Retain all twelve originally selected group decisions in
provenance. These development problem groups are distinct from the earlier
repository-bug studies, but source/test qualification and engineering inspection
have already exposed them. They are not held-out evaluation data. No group may
be replaced because a model succeeds, fails, times out or produces a flat or
unavailable diagnostic. Other reserved groups remain unopened.

## Initial repair and checkpoint rule

1. One initial repair per selected group: eleven planned initial calls. Supply
   its original public statement, whole buggy program, public tests and fresh
   ordinary public feedback, with the same base system instruction as recovery F.
2. Parse the response strictly as a JSON object with one unique key `main.py`
   containing the complete nonempty UTF-8 replacement (at most 262144 bytes).
   No fence stripping, source extraction, patch repair, duplicate keys or fallback
   to the human program. Invalid output is an initial failure, not a manufactured
   generated checkpoint. Preserve raw text, finish reason and charge.
3. Run each valid replacement against every public case. If all pass, stop that
   group's public policy; later private failures remain false acceptances, never
   triggers for further calls. A syntactically invalid but materializable program
   may fail publicly and remains eligible, with empty/unavailable diagnostics.
4. A materializable initial replacement with at least one public failure is an
   eligible generated checkpoint. Do not condition eligibility on private tests,
   score availability, score spread, apparent repairability or source length
   beyond the declared contract. Finish the eleven initial slots before recovery.
5. Acquire one snapshot on each eligible checkpoint: for every public test, one
   fresh ordinary and one monitoring-covered execution. Require semantic agreement
   with the stored feedback; otherwise the entire diagnostic is unavailable.
   Reuse this snapshot across draws, with its full cost recorded. Never reacquire
   an unhelpful snapshot. Retain all unavailable/flat/empty checkpoints.

## Three matched recovery conditions

Each eligible checkpoint has three draws in each condition: up to 99 recovery
calls, **110 total model calls** including the initial eleven.

- **F / feedback:** statement, current full source, public cases and stored feedback.
- **N / neutral:** the same fields plus every covered source location in canonical
  source order. Association fields explicitly say `not supplied`.
- **S / scored:** the identical excerpts/order, plus exact failing/passing coverage
  counts and squared Ochiai fractions from public tests only.

If coverage is unavailable, N and S receive the same generic unavailable flag.
These calls remain separate outcomes. All arms use the same solver and generation
allowances; N/S are not token-length matched. Recovery responses receive the same
strict parser and verifier. Each draw starts from the shared failed checkpoint,
not another arm's patch, result or conversation. Freeze a deterministic balanced
arm order and paired draw seeds; seed support is not proof of deterministic or
common random sampling by the service. No changes or treatment inspection while
collection is active.

## Solver and resource envelope proposed for the launch freeze

Start with `google/gemma-3-4b-it`, Parasail/BF16, no provider fallback, temperature
0.7, seed 20261030, output cap 4096 tokens, input reservation 65536 tokens.
The [public endpoint metadata](https://openrouter.ai/api/v1/models/google/gemma-3-4b-it/endpoints)
observed on 2026-10-30 lists $0.04/M input and $0.05/M output tokens. Verify the
exact endpoint, supported parameters, context and price ceilings before launch.
Metadata is not a successful availability probe. Do not rotate keys after errors.

The larger input reservation covers repeated source excerpts. Admission uses
the adapter's conservative UTF-8 bytes plus 4096 framing allowance, and checks
native usage against the reservation on settlement. This is not an exact Gemma
tokenizer measurement. Known source-size measurements and Qwen token counts do
not guarantee that Gemma emits a valid or sufficient repair. No source truncation
or selected-case removal is allowed to force a request under the limit. An
over-limit request remains a missing selected opportunity; it cannot be replaced.

| Budget item | USD |
| --- | ---: |
| Previous cumulative commitment, including 14 uncertain reserves | 0.25463059 |
| Maximum single-call reservation | 0.00282624 |
| All 110 planned maximum reservations | 0.31088640 |
| Proposed study allocation | 0.32000000 |
| Prior commitment plus proposed allocation | 0.57463059 |
| Existing cumulative ceiling | 0.60000000 |

The $0.32 is a proposed suballocation under the standing instruction to proceed
within $0.60, not a new explicit numerical human approval. It becomes operational
only in the separately declared, tested single-use funding freeze. Preserve all
prior reserves; charge receipts once; retain full uncertain-call reserves. At
least 60 seconds between admissions, one request in flight, no retry, fallback,
resumption or automatic successor after an operational interruption. Finish
received data offline; preserve every never-sent, rejected or uncertain slot.

Record generation charges/latency/tokens, parsing and projection time, all public
and evaluator executions, acquisition time, preflight and independent replay work.
Report actual collection costs separately from per-policy deployment accounting.
Do not divide a shared snapshot cost by draws when estimating a policy that would
need to acquire that snapshot itself. Common initial work belongs to every policy.
No inference of equal total resources follows from equal generation limits.

## Outcomes, analysis and advance criterion

Full repair means every public and private evaluator case passes under the frozen
ASCII-whitespace-token comparator and native limits. Private tests never enter
requests, acquisitions, initial stopping or admission decisions. Keep invalid
responses, regressions on previously passing public cases, false acceptances,
timeouts and output limits as observed failures. Missing is distinct from failure.
Run private evaluation only after model collection is terminal.

Primary conditional analysis uses all eligible generated checkpoints, with each
checkpoint weighted equally and three draws averaged within it. Report S−N full
repair difference, the paired difference in each draw, and S−F in the same table.
Also show the complete eleven-group flow, initial repair outcomes, end-to-end
policy outcomes and all exclusions. Do not treat three draws as three independent
bugs or switch the primary contrast to a more favorable one.

The **practical target is at least +10 percentage points S−N**: an extra full
repair per ten recovery opportunities would justify testing whether the extra
diagnostic cost is worthwhile. This is a development target, not a statistically
established minimum effect or an equal-resource result. With at most eleven
groups, one checkpoint can materially change the estimate; this pilot is not
powered to confirm a ten-point population effect. Numerical sensitivity and
the executable analysis must be checked on synthetic positive, null, regression
and missing banks before launch.

Advance to planning independent replication only if all of these hold:

1. Every initial opportunity and every eligible recovery opportunity has a known
   result, with audited receipts and complete verification; no missing cells.
2. At least six materializable generated public-failure checkpoints were produced.
   Fewer means insufficient calibration, even if the small observed effect is large.
3. At least three different checkpoints have full S repairs in at least two draws.
4. S−N is strictly positive in each of the three draws and at least +0.10 overall.
5. S−F is nonnegative in each draw and overall. This does not replace the primary.

A complete bank failing a criterion does not advance. An incomplete bank is
inconclusive: retain missing outcomes, report finite best/worst completion bounds
on the fixed eleven-group end-to-end panel, and do not publish a conditional
mean/bootstrap or a passed gate from only complete cases. If initial outcomes are
missing, the eligible checkpoint count is itself incomplete. No p-value or
significance claim is planned. Replicates assess repeatability within this sample,
not independent generalization.

A passed screen permits only designing an untouched, separately frozen replication
with adequate precision and total-resource comparisons. It never enables selector
training automatically. Only a replicated useful intervention may motivate a
selector trained on development bugs and tested against the best fixed strategy
on further untouched groups. The full user goal remains unachieved meanwhile.
