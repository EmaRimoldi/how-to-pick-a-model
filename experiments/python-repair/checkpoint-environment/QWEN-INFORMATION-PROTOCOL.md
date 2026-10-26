# Qwen public-trace information calibration

Status: prospectively declared on 2026-10-26 after the user's instruction
“Procedi, set the new goal.” No outcomes from this study were inspected when
setting this design. The completed [solver screen](results/solver-qwen-20261026/README.md)
qualified the model; its 32 historical responses are not concurrent controls.
This is a new study, not a retry or successor to any closed collection.

## Question and scope

At an identical failed checkpoint, does adding a bounded trace of the candidate's
execution improve complete repair compared with the same focused public feedback?
This is the first milestone of the [operative research goal](GOAL-AMENDMENT-20261026.md).
The final target is a prospective diagnostic-acquisition policy that beats the
best fixed policy on untouched bugs after charging acquisition and selection.
The present one-generation experiment cannot establish that policy advantage.

## Inputs and interventions

Retain all twelve immutable JSON-current candidate artifacts from the completed
27B contract bank. Eligibility is exactly its eight public failures, including
the bugs Qwen did not solve in its compatibility screen. Seven eligible bugs are
from youtube-dl and one from httpie. All are inspected development examples;
there is no fresh test set or population-generalization claim. The other four
public passes, their hidden failures and specification ambiguity stay visible
in provenance without intervention. Neither specifications nor tests change.

Each eligible checkpoint has four draws of each of two arms (64 calls):

- `focused`: the candidate code, instructions, public cases and existing public
  feedback, with the failing public case highlighted.
- `focused_trace`: exactly that payload plus the bounded execution trace of the
  same candidate on the same failing public case. No reference patch, evaluator
  case, hidden answer, generated expected answer or historical solver output is
  supplied. Unavailable or truncated traces remain part of the intervention.

Use the existing public-only diagnostic adapter and independently reproduce every
source feedback and trace before dispatch. No alternative case is chosen after
seeing a trace or response. The original preservation language and JSON contract
stay unchanged. Raw feedback and restart are future fixed-policy comparators;
this two-arm study isolates the addition of a trace over matched information.

Pin `qwen/qwen3-coder-next`, `parasail/bf16`, provider Parasail, BF16,
temperature 0.7, JSON-object output, maximum 4,096 output tokens and the existing
32,768-token input reservation bound. The transport's 4,096-byte framing margin
stays intact. Seed 43130 fixes the shuffled checkpoint/draw blocks; alternate
arm orders give 16 blocks in each order. Within a block both arms have the same
provider seed, without assuming deterministic providers. All request identities
and bodies must be disjoint from every old planned request, including missing
and never-sent requests. No fallback, retry, resumption, successor or key rotation.

## Primary analysis and development screen

The only arm contrast is **focused_trace minus focused** in full public-and-
evaluator success, over all 8 × 4 planned cells per arm. Keep unusable outputs as
observed failures. Keep unknown outcomes missing, never discard their bug.
Report public false acceptance, public-score regressions, usable artifacts,
actual API charges, unresolved reserves, prefix cost and local execution time.
Full success is not proof of all semantic requirements.

For a complete bank, report the paired mean difference averaged over eight bug
clusters and the existing descriptive 10,000-resample bug bootstrap (seed 43123).
There is no confirmatory p-value. Four draws are nested observations, not four
independent bugs. For an incomplete bank, report selected-cell finite bounds,
null means/bootstrap and an inconclusive screen. Do not condition on completed
pairs or success and do not replace the primary contrast with a favorable metric.

The engineering screen retains the earlier information-study thresholds:
complete bank; at least three bugs with at least two full trace-arm successes;
at least four net additional full successes (12.5 percentage points); and a
strictly positive net advantage in each draw half {0,1} and {2,3}. These thresholds
are a development filter, not a statistical guarantee or permission to train a
selector. Report all regressions and false acceptances even if it passes. A pass
permits only a separately frozen equal-total-budget calibration on new examples;
a null or incomplete result does not justify fitting a trace-acquisition policy.
No interim treatment reads, tuning, early stopping for results or gate changes.

## Resources and launch conditions

The agent declares a separate **$0.47** allocation within the user's retained
**$0.60** cumulative ceiling, under the standing instruction to continue and the
latest approval to proceed. This is not a newly user-typed monetary amount.
Carry **$0.06942739** exactly once, including eight historical unresolved calls.
The per-call reservation is $0.00720896; 64 maximum reservations are $0.46137344.
Maximum design commitment is $0.53080083; carry plus the whole new allocation is
$0.53942739. See [authorization](QWEN-INFORMATION-AUTHORIZED.json).

Spacing is at least 60 seconds between admissions. Inspect live endpoint support,
pricing bounds and credit coverage read-only before launch. The cause of the old
HTTP 429 errors remains unknown; neither a reset nor future availability is
assumed. The first error stops this study and preserves all charges/reserves.
No additional API operation is authorized to discover whether a failed call ran.

Require a reviewed exact packet, public-only projection and replay, passing full
repository workflow, clean committed source, green CI, source freeze and a
single-use study claim. While live, check only progress, identities and accounting;
do not change frozen sources. After termination, audit all receipts, export inert
sources and independently replay public/evaluator records and diagnostic inputs.
Use `report_repair_information_study.py` and
`verify_repair_contract_evidence.py`; inspect any generated figures visually.

A one-call cap is not equal realized spending. Count the diagnostic's extra input
tokens in each actual receipt; report acquisition executions/seconds and source
prefix costs per hypothetical deployment, even if cached for this research bank.
Do not rebill those counterfactual prefixes as current API expenses or convert
local seconds into invented dollars. Collection pacing is operational overhead,
not evidence about deployed agent latency. Later policy comparisons must declare
both total API and local-runtime envelopes and include failed calls and selection.

## Decision after delivery

If this intervention is useful and repeats on separate development bugs, compare
never-diagnose, always-diagnose, direct retry and restart under equal total limits.
Only then fit a selector using information available **before** acquisition,
compare with calibrated expected-value and relevant fact-selection/two-candidate
baselines, and freeze untouched bugs/projects for evaluation. Model scaling and
switching are later hypotheses requiring controlled protocols. This study makes
no causal comparison with Gemma and establishes no scaling law or novelty claim.
