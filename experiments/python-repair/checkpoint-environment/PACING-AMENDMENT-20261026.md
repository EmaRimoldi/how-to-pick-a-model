# Manual pacing amendment after a provider rate limit

The user delegated the reviewed continuation with **“Fai come ritieni necessario.”**
within the existing $0.60 cumulative cap. This amendment exercises that delegation
only for still-unstarted original trajectories; it does not add tasks, repeat any
admission or enlarge the budget. No treatment statistics were inspected to make
this operational decision.

## Second segment and accounting

The authorized successor used commit `b539d45fca5bccfa6bedbefac8dad3df76310db3`
and freeze `dc8154811d06aec28cdd4b3dc5210b90f7906a6334181ec2e8ec58a4d2f0c4ee`.
It obtained 32 accounted responses, then stopped on admission 33 with **HTTP 429**.
No raw completion payload was received for that request. Its $0.00151552 reserve
is retained, and the request is not retried. The first segment remains immutable.

Across both segments there are **42 saved observations and 44 admissions**.
Known charges are $0.00183994 and the two unknown reservations total $0.00303104;
the conservative cumulative commitment is **$0.00487098**. Nine trajectories
finished, two started but did not finish, and thirteen never started. Both
interrupted trajectories and all their uncollected states/draws stay incomplete.

A read-only key check indicated a paid account, sufficient credit and a
`requests: -1` rate-limit field; this does not establish the provider's rate cap.
OpenRouter's [pricing documentation](https://openrouter.ai/pricing) says paid
model limits normally come from the provider rather than the account plan.
HTTP 429 does not prove that our previous unknown failure had the same cause,
nor establish that an unsuccessful request was unbilled. Both reserves remain.

## Reviewed continuation

The [paced config](PILOT-PACED-CONTINUATION.json) enumerates the thirteen still
untouched trajectories. It is a subset of the twenty-two already authorized
for continuation. Their model/provider, task hashes, prompt contents, temperature,
paired seeds, verification, prefix/branch design and future allowance are unchanged.

The only serving change is a minimum **15 seconds between dispatches of distinct
new requests**. This is a conservative pacing choice, not a measured guarantee
against rate limits. It is recorded separately from model settings. No failed
request is retried and no provider fallback is enabled. The adapter now also
retains a safe Retry-After header if present. Another error stops collection.

The per-segment allowance is `$0.60 - $0.00487098 = $0.59512902`. At most 195 new
calls reserve $0.29552640, for **$0.30039738** including all previous commitments.
The source freeze must precede calls. A recursive lineage audit validates every
ancestor's immutable files, excludes all previously started trajectories, rejects
overlapping admissions and accounts for inherited commitments once. A unique
successor claim prevents two successors from spending the same remainder.

Report segment and pacing changes alongside outcomes; the bank is incomplete
and remains development data. Pacing time is collection overhead, not model
inference time or a demonstrated deployment cost. Do not pool observations as
independent bugs or claim a held-out selector result from this calibration.

## Final operational segment (recorded before treatment analysis)

The 15-second segment, frozen at `26c01a6`, stopped on HTTP 429 after 34 saved
responses and 35 admissions, with no Retry-After header. It completed five
trajectories and partially started a sixth. Across the three immutable segments,
76 responses and 79 admissions are retained: 14 trajectories finished, three
remain partial and seven were never started. Known charges total $0.00379621;
three uncertain reserves total $0.00454656. Commitment is **$0.00834277**.

The user's delegated exception still covers the seven untouched trajectories,
a subset of the authorized original 22. The [final continuation config](PILOT-FINAL-CONTINUATION.json)
excludes every started trajectory across all ancestors and preserves their
receipts/reserves once. It changes only dispatch spacing to **60 seconds**;
this is a conservative serving choice, not an established provider requirement.
No model/provider, task, seed, prompt, action or verifier changes. At most 105
new calls reserve $0.15912960, at most $0.16747237 with prior commitments.
The segment allowance is $0.59165723 under the same $0.60 cumulative cap.

This is the last operational continuation of this pilot: another provider error
closes the incomplete bank for descriptive analysis. No treatment outcomes were
inspected to choose this cutoff. Successful completion would give at most 21 of
24 complete trajectories, retaining the three partial ones. No learned selector
or action-efficacy result can be claimed before auditing and analyzing the bank.

The offline calibration reporter is prepared and tested on scripted data. Its
policy table uses a common complete-checkpoint cohort for all five controls,
averages within bugs before across bugs, and retains missing-draw bounds for
all observed eligible checkpoints. It separates fresh replay timings from
reproducible outcome/cost fields and makes no evaluator-oracle selection.
