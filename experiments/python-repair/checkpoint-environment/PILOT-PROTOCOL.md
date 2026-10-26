# Gemma 3 4B development calibration — draft

Status: collector and pinned provider adapter implemented and tested offline;
no model responses yet. The user subsequently authorized a new **$0.60** cap,
including unresolved reservations, recorded in [PILOT-AUTHORIZED.json](PILOT-AUTHORIZED.json).
The initial unfunded proposal remains in [PILOT-DRAFT.json](PILOT-DRAFT.json).
The source/task freeze is created from the committed authorized configuration
before any model calls; this document alone is not that freeze.

## Question and population

Can the intended solver produce natural, partially useful patches on these
function-level Python bugs, and do keeping versus discarding a failed patch have
different recovery outcomes? This is development calibration, not a confirmatory
selector evaluation. All twelve [development tasks](development/README.md) are
retained, including easy, unsolved, malformed and technically failed attempts.
Ten tasks come from youtube-dl; this is not a representative software benchmark.
Public and evaluator cases are separate but both are published development data.

No model training or scientific success threshold is selected in this pilot.
Past HumanEval+, MBPP+ and BigCodeBench studies remain completed evidence and
cannot become untouched evaluation data again.

## Proposed sampling design

- Twelve tasks, two independently sampled prefix trajectories per task.
- At most three sequential prefix attempts, starting from the original buggy
  files and their public-test feedback. Each next prefix attempt receives the
  last prefix artifact and feedback, not a conversational transcript.
- After every valid generated prefix artifact that fails public tests, save a
  checkpoint and obtain two independent draws for each action: continue and
  restart. A malformed response has no new artifact: retain and charge it, and
  terminate that prefix as a format failure rather than silently retrying it.
- Continue supplies the current failed patch. Restart supplies the original
  buggy files, not an empty program. Both receive identical task specification,
  public cases, latest public feedback, solver settings and remaining allowance.
  The system instruction explains that feedback can refer to another file state.
- Branch results never update the original prefix. After all branch draws, the
  original prefix continues from its own last checkpoint. No useful branch is
  selected to manufacture better future training states.
- Stop a prefix on a public pass, even if evaluator checks find it incorrect.
  Evaluate both suites for every valid artifact, but never feed evaluator
  outcomes into another request, checkpoint decision or candidate selection.
- Precompute task/replicate order; counterbalance action order within each draw
  using the fixed schedule seed. Paired action draws use the same request seed;
  different draws/prefixes use distinct derived seeds. Seed support is not a
  promise of identical provider random numbers or deterministic API behavior.

The maximum is 24 prefix trajectories, 72 prefix calls and 288 branch calls:
**360 completions**, before public stopping or exhaustion. This is an upper
bound on calls, not an authorized spend or a guaranteed sample size. Checkpoints
and replicates from one bug are dependent observations, not additional tasks.

## Candidate selection and comparisons

The saved bank supports these declared one-checkpoint diagnostic policies:

| Policy | Candidates paid for | Selection |
| --- | --- | --- |
| Continue one | Continue draw 0 | Return that candidate |
| Restart one | Restart draw 0 | Return that candidate |
| Continue two | Continue draws 0 and 1 | Higher public pass count |
| Restart two | Restart draws 0 and 1 | Higher public pass count |
| Mixed two | Continue draw 0 and restart draw 0 | Higher public pass count |

Malformed candidates rank below executable candidates. Ties use a fixed,
outcome-independent order; the mixed policy counterbalances its tie order by
group identity. Selection code receives only candidate IDs and public scores.
The selected candidate's evaluator result is looked up afterwards. Do not report
the existence of any correct candidate as deployed selection performance.

Mixed two is an adaptation inspired by PATSSEL, not a reproduction: it uses the
task's provided public tests and feedback-matched original-file restart, without
its learned verifier or problem-only regeneration. Continue two and restart two
control for the two candidate generations. One-candidate policies deliberately
spend less; their comparison does not establish equal actual spending.

For both transports the per-checkpoint allowance is two conservative request
reserves. This allows all five diagnostic policies; it does not make a
one-candidate policy a complete optimal consumer of the allowance. A subsequent
policy evaluation must specify how remaining budget is used and collect actual
suffixes after each selected action. The current bank cannot identify arbitrary
multi-step policies by stitching branches together.

## Accounting and interruption

Keep research collection expenditure separate from counterfactual policy cost.
The collection ledger pays each physical call once. A diagnostic policy is
charged its shared prefix once plus all candidates it generates, including the
unselected one. Selection overhead and verifier runtime must also be reported.
The scripted transport's ledger is explicitly in simulated USD; actual API
calls and charges are zero, and its handwritten outcomes are not model evidence.

Persist the exact request and an admission reservation before sending. Preserve
the response before settlement. A missing/uncertain response or invalid receipt
must retain its reservation and stop collection. Never automatically resume an
existing run or repeat an admitted attempt. Stop before starting a matched set
whose conservative reservation cannot fit. Uncollected outcomes are missing,
not solver failures. Keep partial runs auditable without a completion seal.

The production adapter validates account credit, pinned
model/provider identity and current prices, enforces request and campaign ceilings,
records reported token/cached-token usage, and rejects implicit fallback/retry.
The historical insurance assumptions are not automatically adopted by this
new collector. Provider error billing remains uncertain unless verified. A
known charge larger than its original reservation is included at its larger
reported value in conservative committed cost; it stops collection and is not
hidden behind the reservation. A global campaign claim prevents duplicate launch
under another output directory, including after failed preflight. Manual review
and explicit new authorization are required for any subsequent campaign.

## Provider and cost proposal

Public endpoint metadata checked on **2026-10-26 UTC** lists Gemma 3 4B through
Parasail/bf16 at **$0.04 per million input tokens and $0.05 per million output
tokens**. The endpoint reports seed and JSON-format support. This is a serving
configuration, not access to immutable model-weight hashes. Pricing and endpoint
availability are rechecked before the first generation; changes can abort the
run. Sources: [model page](https://openrouter.ai/google/gemma-3-4b-it),
[endpoint API](https://openrouter.ai/api/v1/models/google/gemma-3-4b-it/endpoints).

The draft fixes temperature 0.7, a 4,096 output-token cap and a 32,768 input-token
admission bound. Text bytes plus 4,096 framing allowance must fit before sending;
reported native token usage is checked afterwards. This conservative heuristic
is not a proof about every provider tokenizer/template. Oversized requests stop
without being sent; outputs truncated at the cap remain paid format failures.

At the declared price ceilings, reserve
`(32768 * 0.04 + 4096 * 0.05) / 1e6 = $0.00151552` per physical call. At most 360
calls reserve **$0.54558720**, excluding local compute and account top-up fees.
The user authorized the proposed **$0.60 new campaign cap**, including uncertain
reserves. This covers the design with margin. The per-checkpoint future allowance is $0.00303104; prefix
cost is additional and reported once. Actual usage costs, including cached-token
details, come from receipts rather than this bound.

Routing pins `parasail/bf16`, precision, price ceilings and required parameters,
with fallbacks disabled. Only text JSON completions are supported. The adapter
stores the exact provider payload before sending, retains the received payload
before settlement, and uses account-charge `usage.cost`, not an upstream cost
estimate. Sources: [routing](https://openrouter.ai/docs/guides/routing/provider-selection),
[usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting).

## Development report and gate

Report prefix success/failure/format errors, public-score progress and
regressions, valid failed checkpoints, per-action success over repeated draws,
public false positives, missing cells, actual expenditure and verifier runtime.
Show task-level results and aggregate at the bug level; no confirmatory p-values
or universal performance claims from this small, inspected pool. Preserve
identical/no-op artifacts and cases where both actions fail or both succeed.

Do not train a selector just because a single draw differs. Use replication to
check whether action complementarity exceeds sampling noise and whether enough
distinct bugs support a learnable decision. If the model always succeeds, always
fails, or one action consistently dominates, record that finding and reconsider
the development setting before selecting an independent evaluation pool.

A subsequent selector protocol must fix task/project splits, sample size,
primary budget and effect threshold, uncertainty and missing-data handling,
predictor capacity, baseline tuning and deployment-cost accounting before
evaluating untouched bugs. History may help a limited predictor; it does not
alter a stateless solver's distribution conditional on its complete request and
execution state. Model-size scaling is a later, separately funded experiment.

## Remaining prerequisites for a real pilot

1. New monetary cap obtained: **$0.60**, including uncertain reserves. Previous
   campaigns remain closed and do not contribute further funding.
2. The funded copy has status `authorized_development_pilot`,
   `live_calls_enabled: true`, the actual `monetary_authorization_usd` and an
   `authorization_reference` to the new user approval. Preserve `campaign_id`;
   do not invent another ID to bypass an interrupted campaign's claim.
3. Commit and review source changes, then run `freeze --config <funded-config>
   --output <new-freeze.json>`. This is offline and pins tasks, prompts, verifier,
   settings, source commit, Python/platform and accounting. A dirty checkout or
   an underfunded maximum design is rejected.
4. Supply a key only through the private process environment. Run `live --input
   <freeze.json> --output <new-run-directory>` after sandbox preflight. The launcher
   rejects changed source/tasks/config, records its single-use campaign claim,
   and checks account/key credit and current endpoint metadata before generation.
5. Launch one collector in a fresh directory. Save all reservations and outputs;
   its completion marker must not reactivate historical research automations.
