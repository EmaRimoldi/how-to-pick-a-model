# Repair-interface cue control, v1

Status: prospective development protocol, fixed before any call in this study.
Identity: `repair-interface-cues-v1`. It follows the closed information study;
it is not a continuation and cannot replace any historical missing outcome.

## Question and fixed interventions

Does removing a preservation cue and explicitly permitting internal edits improve
full repair at the same already-failed checkpoint? This isolates two interface
cues. It does not identify psychological anchoring, generic model capability,
the effect of JSON output, or the value of acquiring execution traces.

Use all twelve `json_current` candidates from the complete archived Gemma 27B
bank, SHA-256 `f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913`.
Eight fail public tests and receive the intervention. Four public passes remain
in provenance without intervention. Eligibility uses no evaluator score. All are
exposed development bugs; ten of the original twelve come from youtube-dl.

| Arm | Provenance clause | Explicit permission to edit helpers |
| --- | --- | --- |
| `original` | Retained | Absent |
| `claim_removed` | Removed | Absent |
| `helpers_explicit` | Retained | Added |
| `both` | Removed | Added |

Remove only `; upstream definitions are unchanged.` from the exact
`# Adapted from ...` comment, replacing it with a period. Keep upstream
attribution, license text, line count and the entire executable syntax tree.
Do not change identical text in string literals or other comments.

The added instruction is exactly: “Every supplied function, class and helper may
be changed when needed to satisfy the specification and public tests. Preserve
the external callable's name, arguments and return contract.” It supplies no
fault location, reference patch or additional expected result. The original
instruction remains otherwise unchanged. All arms receive the identical raw
public suite and preceding feedback; no trace, focused repetition or history is
added. The external task, evaluator, output contract and scoring stay fixed.

## Sampling and operational boundary

Four fresh draws × four conditions × eight failures = **128 requests**. The
original arm is sampled again as a concurrent control; old answers are not its
replicates. Seed base 43126 generates distinct task/draw seeds shared across the
four arms. Task/draw blocks are deterministically shuffled; cyclic condition
orders place each arm in each position once per bug. Provider seed support is
not a determinism guarantee. Exact request bodies are frozen, and none may equal
a prior 27B or information-study body, including uncertain and unsent cells.

Use `google/gemma-3-27b-it`, `deepinfra/fp8`, FP8, temperature 0.7, JSON object
mode, at most 4096 output tokens and a conservative 32768 input-token admission
bound. No fallback or provider/model change is allowed. Price ceilings remain
$0.08/$0.16 per million input/output tokens; live preflight must confirm a
compatible endpoint, supported parameters and adequate credit before admissions.

After the preceding 429s, this new design uses a minimum **30 seconds between
admissions** (at most two per minute). Slower pacing is an operational precaution,
not evidence that a rate limit has reset or that the provider will succeed. Make
no extra generation health check. The first uncertain/error request stops the
study, retaining its reservation. No retry, resume, recursive successor, fallback
or key rotation is enabled. One fixed study claim prevents duplicate launches.
Do not modify source or inspect treatment statistics while the collector runs.

The separate [allocation](INTERFACE-AUTHORIZED.json) is **$0.43**, declared under
the user's standing instruction to continue, within the retained cumulative
$0.60 ceiling. Carry **$0.04058467** once, including seven unresolved historical
calls. Maximum new reservations are $0.41943040; maximum design commitment is
$0.46001507. This allocation does not alter any closed study's cap. Local compute
is reported separately from API dollars. Every prior reserve remains unresolved.

## Frozen analysis and gate

Primary outcome: full public-plus-evaluator pass. Primary contrast:
**`both` minus `original`**, averaged over the eight bugs, with four draws each.
Secondary contrasts are marginal claim-removal and explicit-permission effects
(each averages over the other factor), and the difference-in-differences
interaction. They cannot replace an unfavorable primary result. Report all
conditions even when none is useful.

Record usable artifacts, public passes, false public acceptance, partial-score
improvements, regressions and syntax-edit categories relative to the actual
request files. Syntax identity is not semantic equivalence. More edits or fewer
copies without more complete repairs does not meet the objective.

For a fully sealed bank, report descriptive paired bug-cluster bootstrap intervals
with 10000 resamples, seed 43127. These describe eight selected clusters, not a
confirmatory population effect. For an incomplete bank, keep all 128 cells and
report worst/best selected-cell bounds, with no complete-bank mean, bootstrap or
passed gate. Do not impute missing calls as failures or analyze only complete bugs.

The engineering screen requires all 128 outcomes, no accounting overrun, complete
repairs in `both` on at least three distinct bugs with at least two successes per
four draws, at least four net successes over `original`, and positive net gain
in both draw halves {0,1} and {2,3}. A pass permits only **independent interface
calibration**. It does not select a deployed policy, authorize training, certify
a causal psychological mechanism, or establish action complementarity.

Charge every admitted call, longer prompt and unresolved reservation. Report
prefix API cost once per counterfactual deployment without rebilling it into
the actual ledger. Keep source verification, response verification and provider
latency separate. Equal per-call ceilings are not equal realized spend or a
fixed-budget policy comparison. Operational pacing is not a policy action cost.

## Reproduce and deliver

```bash
.venv/bin/python scripts/prepare_repair_interface_study.py \
  --output runs/repair-interface-packet.json

.venv/bin/python scripts/report_repair_interface_study.py \
  --input runs/repair-interface-live \
  --output runs/repair-interface-report --export-evidence

.venv/bin/python scripts/verify_repair_contract_evidence.py \
  --input runs/repair-interface-report --output runs/repair-interface-replay.json
```

Preparation and reporting never call a model. Live execution is only through
the existing separate collector after a clean committed freeze and CI review.
At termination audit all receipts and exact prompt projections, export inert
sources, independently re-execute saved evaluation inputs, and retain nulls and
missing data. Update the draft PR and pause its dedicated monitor after delivery.
