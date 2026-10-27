# Distinct streaming public-trace development calibration

Study: `repair-qwen-stream-trace-development-v1`. Prospective specification,
recorded before any calls in this study. Code: `vao.repair.stream_information_study`;
collector: `scripts/collect_repair_contract_probe.py`; report:
`scripts/report_repair_information_study.py`. This is development evidence for the
first milestone in GOAL-AMENDMENT-20261026.md, not a trained or validated selector.

## Motivation and exposure

The complete solver compatibility control found usable repairs, but both earlier
information banks stopped with missing responses. They stay closed and
inconclusive. The separate one-request wire-envelope check received a complete
receipt beyond the old 1 MiB limit; this supports using an explicit 8 MiB cap,
not a reliability claim or an explanation of earlier connection errors.

All previous outcomes have been inspected. Retain all twelve original source
candidates from the 27B contract study, with the same public-only qualification:
eight saved public failures are eligible (seven youtube-dl, one httpie); four
public passes remain in provenance, including evaluator failures and the known
specification ambiguity. No bugs are newly held out. This is a fresh matched bank
on exposed checkpoints, not completion of old missing cells, replication on
independent bugs or a confirmatory study. No pooling or historical controls.

## Intervention and schedule

Each eligible checkpoint receives four fresh draws in each of two conditions:
`focused` public feedback and `focused_trace`, which adds only the frozen bounded
public execution trace. There are 32 matched pairs and 64 requests. Pair ordering
is shuffled with seed 43135; arms alternate order across pairs, 16 each. Both
members share the model sampling seed and all settings; only `runtime_diagnostic`
differs. Hidden evaluator data never enter selection, diagnostics or messages.

Pin qwen/qwen3-coder-next, Parasail/BF16, JSON-current contract, temperature 0.7,
4096 maximum output tokens, 32768-token input reservation, input/output pricing
ceilings 0.12/0.80 USD per million tokens, no fallback. Use streaming with final
usage and DONE required, explicit 8 MiB wire cap, 180-second idle read and a
300-second wall check at read boundaries (not a hard deadline). Requests are
spaced by at least 60 seconds. New attempt identities and actual provider bodies
must be disjoint from every planned body, even unsent, in thirteen frozen archives.

Initial public feedback and diagnostics must reproduce before dispatch. One
single-use claim; immutable exact-request freeze from clean committed source and
green checks. First provider or evaluator error stops this study. No retry,
resumption, successor, key rotation or replacement of missing cells. During
collection inspect only progress, request identity and accounting. No intermediate
treatment statistics, gate decisions, tuning or outcome-dependent stopping.

## Budget and accounting

A separate bounded allocation of 0.47 USD is declared under the standing user
instruction to continue and retained 0.60 USD cumulative ceiling; it is not a new
amount typed by the user. Carry 0.11785551 USD once, including all twelve old
unresolved reservations. Full allocation plus carry is 0.58785551 USD. Maximum
64 new reservations of 0.00720896 USD total 0.46137344 USD; maximum design commitment
including carry is 0.57922895 USD. Provider preflight must still verify capacity.

Reserve durably before dispatch. Keep all receipts, partial-failure metrics and
unknowns; count max(reservation, observed cost) for uncertain calls, including a
usage amount received before a missing DONE. Preserve every billed unusable
response and paid response without evaluation. Stop on cap or accounting failure.
Report API spending, counterfactual source-prefix costs, diagnostic executions and
local verification seconds separately. This per-call comparison is not a test of
equal total policy cost; no conversion of local seconds into API dollars.

## Prespecified analysis and decision

Primary and only arm contrast: full-public-and-evaluator repair rate for
`focused_trace` minus `focused`, averaged across the eight selected bugs. Report
all 64 planned cells, all twelve source candidates, false positives, regressions,
truncations, costs and missingness. For a complete, uncapped bank report the
paired bug-cluster descriptive bootstrap (10,000 resamples, seed 43123). For any
incomplete bank keep mean/bootstrap null, finite best/worst bounds on all selected
cells, and an inconclusive gate. No imputation or complete-case efficacy claim.

Retain the previously specified development screen unchanged: complete bank,
at least three bugs with two full trace successes each, at least four net
additional trace successes (12.5 percentage points), and strictly positive net
trace advantage in both draw halves {0,1} and {2,3}. This is an engineering screen,
not a significance test, proof of per-instance complementarity or permission to
train a selector automatically. A null screen means useful trace benefit is not
demonstrated and the intervention needs reconsideration.

After termination audit requests, SSE receipts/metrics and all ledger entries;
export inert frozen sources and independently re-execute public/evaluator tests
and public diagnostics. Raw SSE wire bytes are not archived; saved wire hashes
and metrics cannot independently reconstruct the original wire stream. Publish
all results, including nulls and failures. Even a positive screen requires
separate bugs, repeated benefit, total-resource fixed-policy baselines and a
prospective pre-acquisition selector evaluated on untouched grouped bugs before
the overall goal can be met. No causal model-size or transport comparison.
