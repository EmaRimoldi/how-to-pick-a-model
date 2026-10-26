# Python repair checkpoint environment

**Current result: the [independent extension trace calibration](results/information-extension-stopped-20261026/README.md)
is interrupted and inconclusive.** It received 9/24 responses on three additional
development bugs: four focused-feedback repairs and two trace-assisted repairs.
Two requests are uncertain and thirteen were never admitted. Primary bounds
span −75 to +50 percentage points; mean/bootstrap remain null. No trace benefit,
absence of benefit or selector advantage follows. This study cannot resume.

The earlier [matched Qwen information bank](results/information-qwen-stopped-20261026/README.md)
remains separate: 18/64 responses, three trace versus two focused repairs, and
46 missing cells. Its unchanged primary bounds are −68.75 to +75.00 points.

The preceding [Qwen compatibility screen](results/solver-qwen-20261026/README.md)
passed with 10/32 complete repairs and repeated success on three bugs. It
qualified a solver, not an acquisition policy. The final user goal is active:
learn a cost-aware diagnostic-acquisition selector and validate it against the
best fixed policy on untouched bugs under the same total resource envelope.

Read the [current goal amendment](GOAL-AMENDMENT-20261026.md) and
[complete solver findings and replay](results/solver-qwen-20261026/README.md).
The user-directed goal is to learn when acquiring public execution evidence is
worth its cost before another repair, conditional on a useful intervention.
The [diagnostic adapter](DIAGNOSTIC-PREPARATION.md) already supplies bounded
public-only traces. All twelve source candidates remain recorded; eight expose
public failures and four do not trigger recovery. The [source coverage audit](results/solver-qwen-20261026/trigger-coverage-audit.json)
shows why conditional recovery success cannot substitute for end-to-end acceptance.

| Development study | Preserved outcome | Status |
| --- | --- | --- |
| [Original 4B recovery pilot](results/gemma4b-calibration-20261026/README.md) | 84 responses; no observed recovery success; four uncertain calls | Closed, incomplete |
| [4B contract control](results/contract-deepinfra-20261026/README.md) | 36 responses; 1 full repair | Gate failed |
| [12B contract control](results/contract-gemma12b-20261026/README.md) | 36 responses; 2 full repairs | Gate failed |
| [27B contract control](results/contract-gemma27b-20261026/README.md) | 36 responses; 3 full repairs on two bugs | Gate failed |
| [Public-information probe](results/information-stopped-20261026/README.md) | 65 responses; no full repair; 31 unknown cells | Closed, inconclusive |
| [Interface control](results/interface-stopped-20261026/README.md) | 44 responses; no full repair; 84 unknown cells | Closed, inconclusive |
| [Qwen compatibility control](results/solver-qwen-20261026/README.md) | 32 responses; 10 full repairs; three bugs solved in both draw halves | Screen passed; subsequent information bank inconclusive |
| [Matched Qwen information](results/information-qwen-stopped-20261026/README.md) | 18/64 responses; 3 trace versus 2 focused full repairs; 46 unknown | Closed, inconclusive |
| [Independent extension trace calibration](results/information-extension-stopped-20261026/README.md) | 9/24 responses; 2 trace versus 4 focused full repairs; 15 unknown | Closed, inconclusive |

These are distinct protocols, not a pooled model-size comparison. Historical
[capability and partial-progress findings](results/capability-comparison-20261026/README.md),
[specification/acceptance audit](results/diagnostic-audit-20261026/README.md),
[interruption](INTERRUPTION-20261026.md), [pacing amendments](PACING-AMENDMENT-20261026.md)
and [one-use information continuation](INFORMATION-CONTINUATION-AMENDMENT.md)
remain preserved. No old collector may be resumed or its missing cells filled.

The [solver protocol](SOLVER-PROTOCOL.md) preserved original public messages and
the JSON contract, pinned Qwen3-Coder-Next/Parasail/BF16 and fixed its engineering
screen before calls. Its complete bank reproduces independently, including all
62 saved verification records. It contains one public false acceptance and
eleven public-score regressions, retained alongside the ten successes.

Cumulative repair commitment is **$0.10576463 / $0.60**, including eleven unresolved
reservations across closed studies. The latest extension calibration paid
$0.00542396 and retained $0.01441792 in two uncertain reserves, within its
separate $0.18 cap. All collectors are closed. Further research requires a
separately reviewed protocol and declared allocation; interrupted banks cannot
be resumed or used to fit a selector.

The [real-bug development pool](development/README.md) adds twelve adapted BugsInPy
tasks with pinned source excerpts, public/evaluator cases, documented exclusions
and reproducible offline qualification. The qualification is engineering evidence; the separate pilot is limited model evidence.

A separate [development extension](development-extension/README.md) now publishes
three qualified Luigi/The Fuck adapters and their separately reported incomplete
model calibration. The original
twelve-task pool and all closed studies retain their identities. The consolidated
[exposure guard](development/exposure-registry.json) covers 174 inspected bug IDs
across ten projects. The [transport review](TRANSPORT-REVIEW-20261026.md) records
the timeout and response-body-reset evidence; the root causes remain unestablished.

The [extension information protocol](EXTENSION-INFORMATION-PROTOCOL.md) fixed
24 matched requests on all three adapters. Its prospective independent-cell rule
retained one uncertain response, waited 120 seconds and allowed later scheduled
cells; the second error stopped the study. The terminal archive independently
replays all 18 saved evaluation records without discrepancies and preserves all
24 selected cells. It never resumes or pools the historical eight-checkpoint bank.

A separately declared [SSE compatibility probe](SSE-COMPATIBILITY-PROTOCOL.md)
prepares three new synthetic payloads under a $0.03 allocation within the standing
ceiling. The opt-in streaming adapter has offline framing, failure and accounting
checks; historical collectors remain unchanged. No live compatibility or research
gain is inferred from those tests. The probe must pass source/CI review before
its single-use launch, and stops on its first error without a successor.

The domain is function-level Python repair: one or two flat, standard-library
modules, a named callable and JSON inputs/outputs. The environment saves complete
artifacts, public verification, progress histories and branch ancestry. It restores
earlier artifacts without changing saved checkpoints.

The original question was whether public progress history predicts the benefit of
keeping a failed patch rather than restoring the original buggy code. The
expanded [related-work review](../../../docs/recovery-related-work.md) identifies
direct precedents; this question is a replication target, not an established
novel contribution. The
finite-expression prototype in [PR 14](https://github.com/EmaRimoldi/how-to-pick-a-model/pull/14)
remains a separate, unmerged design. This implementation starts from current main;
completed HumanEval+, MBPP+ and BigCodeBench studies are unchanged.

## Earlier selector scope, now conditional on useful acquisition

The [2026-10-26 amendment](GOAL-AMENDMENT-20261026.md) is the operative goal.
The original milestones below remain historical context and possible later
comparisons, not a license to skip the failed capability gate or fit a selector.

Build an executable Python selector that chooses **continue from the current
patch** or **restart from the original buggy files** before generating the next
repair. Its inputs are the task, current/original artifacts, public feedback,
optional public progress history and remaining budget. Evaluator tests and
future branch outcomes are never decision inputs. Budget exhaustion and public
success are explicit termination rules, not unbounded additional attempts.

The engineering deliverable is a documented policy interface, an offline replay
demo, fixed-action and two-candidate verifier-selection baselines, reproducible
data/accounting, and a frozen evaluation on untouched bugs. A lightweight
prospective router is a required comparator. A PATSSEL-inspired adaptation must
declare its different restart contract and charge both candidates and selection.

The scientific target is more fully solved tasks at the same declared total API
budget than the strongest development-selected fixed strategy, with comparisons
against the other baselines and actual spending reported. Include prefix work,
selection, failed requests and unresolved reservations; report local verification
costs separately. Preregister the primary budget, meaningful effect size, sample
size, uncertainty method and pass/fail criterion after development calibration
and before evaluation. Do not claim a successful adaptive policy from a favorable
point estimate, an oracle, or predictor accuracy alone. A null result remains an
honest evaluation outcome, not grounds for recycling the evaluation set.

Milestones:

1. Prepare a development-pilot protocol, collector and end-to-end offline demo.
   Freeze the actual request/verification/accounting implementation before calls.
2. Under a new explicit monetary cap, calibrate Gemma 3 4B on the twelve existing
   development bugs. Measure natural partial progress, regressions, recovery,
   sampling variability and cost; all twelve remain development data.
3. Collect matched action outcomes and establish reproducible complementarity.
   Train a selector only if there is useful decision headroom, then compare
   current-state and history-augmented predictors with matched capacity/data.
4. Freeze and evaluate on untouched bugs, grouping all versions and replicates
   of a bug together and separating upstream projects where feasible. Deliver
   the policy, reproducible report and limitations, whether the gain holds or not.
5. As a separately budgeted extension, compare Gemma 3 4B/12B/27B over a common
   task set and budget grid. Measure success, action preferences, selector value
   and costs. Treat this as empirical scaling curves; three model sizes do not
   establish a general scaling law or isolate parameter count as the cause.

The amended goal is active; the full milestones above were not completed. The closed
pilot had a $0.60 cap including uncertain reserves; the funded config
is [PILOT-AUTHORIZED.json](PILOT-AUTHORIZED.json). Closed historical budgets cannot
fund this pilot. A further collection needs a separately reviewed protocol and authorization; the old continuation configurations cannot be reused.

## Run locally

Use the normal environment (`uv sync --dev --frozen`). Planning and saved-run
audits are portable. Candidate execution requires macOS `sandbox-exec`, as in the
existing verifier. There is no unrestricted execution fallback. The pilot's
separate `live` command requires a newly funded, committed source freeze.

```bash
uv run python scripts/prepare_python_repair.py

uv run python scripts/prepare_python_repair.py demo \
  --bundle experiments/python-repair/checkpoint-environment/fixtures/record-normalization \
  --output runs/python-repair-demo

uv run python scripts/prepare_python_repair.py audit \
  --input runs/python-repair-demo

uv run python scripts/prepare_python_repair.py qualify \
  --bundle experiments/python-repair/checkpoint-environment/fixtures/record-normalization \
  --output runs/python-repair-qualification
```

## Development pilot preparation

The [draft pilot protocol](PILOT-PROTOCOL.md) specifies two prefixes per bug,
up to three prefix attempts and two draws per recovery action: at most 360 calls
over the twelve development bugs. The OpenRouter adapter and collector are tested
with mocked transport; a source/budget freeze remains a prerequisite for `live`.
The original draft disables live calls; the separately authorized config records
the new $0.60 cap.
Its synthetic demo tests bookkeeping and actual sandbox verification
using handwritten responses and simulated dollar amounts, never model outcomes.

```bash
uv run python scripts/prepare_repair_pilot.py plan

uv run python scripts/prepare_repair_pilot.py demo \
  --bundle experiments/python-repair/checkpoint-environment/fixtures/record-normalization \
  --output runs/repair-pilot-scripted

uv run python scripts/prepare_repair_pilot.py audit --input runs/repair-pilot-scripted
uv run python scripts/prepare_repair_pilot.py compare --input runs/repair-pilot-scripted
```

The comparison includes fixed one-candidate controls and public-test selection
from two continue, two restart, or one of each candidate. It charges both
candidates plus the shared prefix once, preserves missing outcomes, and cannot
use evaluator outcomes to choose a candidate. These are one-checkpoint
diagnostics, not an evaluated multi-step selector.

Requests, receipts, ledger, checkpoint objects, prefix ancestry, missing sets
and completion hashes are auditable. An interrupted call retains its reserve;
existing run directories cannot be reused. Prefix progression never uses branch
outcomes. Each valid artifact retains public and evaluator verification, so
public false positives are visible without influencing collection.

The proposed Parasail/bf16 endpoint reserves $0.00151552 per call, or $0.54558720
for the maximum design, at the checked public price. This is a conservative API
estimate, separate from the authorized $0.60 cap and local-compute costs; see the
[pricing and launch prerequisites](PILOT-PROTOCOL.md#provider-and-cost-proposal).
Live launch checks a clean source commit, frozen task/settings hashes, account
credit and endpoint parameters/prices. A durable single-use campaign claim
prevents two output directories from reusing the same collection authorization.
No automatic retry, provider fallback, resume or historical monitor is enabled.

Output directories must be new. Existing runs are never overwritten or resumed.
Interrupted runs stay incomplete; their valid prefixes can be audited.
`completion.json` seals an engineering run. It differs from the historical
collectors' `summary.json` and does not trigger the paused research monitor.

## Development fixture

The repository-authored normalizer handles decimal amounts, ISO/local dates,
missing values and type errors. Six public examples guide repair; ten evaluator
cases check other inputs. These finite tests are not an exhaustive correctness proof.
Both suites and the reference are published development fixtures; “evaluator”
means excluded from solver requests and workspaces, not secret benchmark data.

Handwritten artifacts yield **1/6 → 5/6 → 4/6** public passes. The demo saves all
states, restores the earlier partial patch, forks the last failure and verifies
the same handwritten final repair in both branches. These are engineering
assertions, not evidence that either action, model or selector performs better.

## Matched decision interface

| Information/action | Continue | Restart |
| --- | --- | --- |
| Specification, callable and public cases | Identical | Identical |
| Latest public feedback | Identical | Identical |
| Editable files | Current failed patch | Original buggy files |
| Earlier attempts/history sent to solver | None | None |
| Remaining planning budget | Identical | Identical |
| Evaluator cases, reference and scores | Excluded | Excluded |

Restart restores the original problem, not an empty file, and retains the same
feedback. Both prompts explain that feedback may describe a different file state.
Only supplied file contents differ. Continuing means a new observable edit, not
access to hidden model reasoning. History is saved for a future predictor, not
silently added to solver context.

The demo's `$0.01` is illustrative metadata. This offline API has no billing or
model transport and cannot authorize spending. A future collector must reuse
reservation/receipt accounting, including prefix work, different prompt lengths,
failures and selection overhead. Equal limits do not imply equal realized spend.

## Storage and execution

- `objects/<sha256>.json`: immutable task, artifact, evaluation, checkpoint, branch
  and request objects. Task hashes include both suites and provenance.
- `events/<sequence>.json`: linked journal with object references and timestamps.
- `workspaces/`: exact materializations; edits never mutate stored artifacts.
- `completion.json`: runtime/fixture hashes, OS/Python versions, engineering
  outcomes, zero API calls and an audit anchor that detects journal truncation.

Each test runs in a fresh process containing only declared modules, the worker
and current callable arguments. Expected answers stay in the parent, which scores
returned values or exception types. Candidate-reported pass flags cannot establish
success. Evaluator results cannot be attached to a checkpoint as public feedback.
A public pass stops the prefix even if evaluator scoring later finds a failure.

The OS sandbox denies network and user-home access. The environment strips
credentials, probes isolation before CLI execution, limits CPU/output/file sizes
and wall time, and cleans up the process group. This backend has no hard total
memory or total-filesystem quota. Linux execution is not implemented. Timeouts,
syntax errors, worker exits and malformed outputs remain recorded.

## Qualify a real bug

A local task bundle follows the fixture contract:

1. `task.json`: schema version, ID, full public specification, entrypoint, initial
   editable files, public JSON cases and provenance.
2. `evaluator.json`: evaluator-only JSON cases.
3. `reference.json`: corrected files, used only for qualification.

`scripted-attempts.json` is for the synthetic demo only. The Python API supports
snapshot, evaluate, checkpoint, fork, request and materialize for other tasks.

`qualify` repeats both suites twice on buggy and reference versions. It requires
stable outcomes, initial failures on both suites and reference success on both.
Failure returns a nonzero exit status. Qualification establishes reproducibility
of this harness, not model difficulty, test completeness or recoverability.

[BugsInPy](https://github.com/soarsmu/BugsInPy) supplies the adapted development
pool; this is not a full-repository importer. For an adapted function-level task, record
the upstream bug ID, repository URL, buggy/fixed commits, source hashes, license,
runtime requirements and every extraction/change in provenance. Preserve original
sources locally. Reject tasks whose dependencies or semantics cannot be reproduced
with this standard-library contract. Report adapted tasks as adapted tasks, not
official BugsInPy scores. Never manufacture LLM progress from a reference fix.

Select a development pool on technical criteria before model outcomes. Calibrate
the chosen solver on those tasks before interpreting an acquisition intervention.
Every inspected case remains development data. A model pilot needs its own declared
allocation, provider settings and protocol freeze under the user's authorization;
a closed study's unspent allocation does not enable automatic continuation.

## Scientific gate

Before fresh-task evaluation, fix checkpoints, randomized/interleaved branch
order, repetitions, public/evaluator test separation, per-task accounting and
failure rules. Keep every version/checkpoint/replicate of a bug in the same split.
Public bugs may occur in pretraining; new local IDs do not remove contamination.

First establish a reproducible action difference. Only then compare a history-aware
predictor with a capacity/data-matched current-state predictor and the strongest
development-chosen fixed action on fresh tasks. Predict incremental action value,
not merely next-attempt success or a hindsight oracle. Measure additional verified
solutions at the same total API budget; report local costs separately. With stateless
solvers, history can aid a limited forecaster but adds no intrinsic information
beyond the complete current request-to-outcome law.

12B/27B handoffs, an experimental rollback arm, SQL, ATIF export and full-repository
repair are later extensions. Source: `src/vao/repair/`; tests:
`tests/decisions/test_python_repair.py`.

## Offline calibration report

The reporter never calls a model or trains a selector. Only use it after the
last segment ends; interrupted banks require an explicit flag. It follows all
immutable ancestors, audits receipts and prompt projections, and retains the
full selected task/trajectory denominator and incomplete-checkpoint bounds.

```bash
uv run python scripts/report_repair_calibration.py \
  --input runs/repair-gemma4b-development-final-20261026 \
  --output runs/repair-calibration-report --allow-interrupted --export-evidence
# Optional: --reverify executes saved artifacts in the macOS sandbox, with zero API calls.
```

Policy diagnostics use the same complete checkpoints and equal weight per bug.
Descriptive intervals resample bugs rather than treating correlated checkpoints
as independent. Costs include prefix work and discarded candidates. Fresh
replay-selection timings are machine-dependent; all outcome and cost fields
must reproduce independently of those timings. No prospective-selector value or
scaling law follows from this small development pool.

The optional evidence export preserves original relative `runs/` paths inside a
hash-manifested ZIP so lineage can be audited after extraction into a fresh
working directory. Saved model artifacts remain inert JSON; frozen collector
sources are archived as `.txt` and checked against each segment's committed
source hashes. Never modify historical manifests to relocate ancestors. Prefix
progress, regressions, no-op patches and identical action input files remain
visible in the report, including states that offer no artifact intervention.

## Output-contract diagnostic and provider follow-up

The [first contract diagnostic](results/contract-diagnostic-20261026/README.md)
is terminal and inconclusive: three responses on one bug, followed by HTTP 429
on the fourth admission. All 36 planned cells remain visible; 33 outcomes are
missing. The $0.06 study committed $0.00179665 including its uncertain reserve,
bringing the recovery-pilot-plus-diagnostic total to $0.01191076. No format won
the gate and no selector was trained. The [original protocol](CONTRACT-PROBE-PROTOCOL.md)
and portable evidence remain immutable.

The [DeepInfra follow-up protocol](CONTRACT-DEEPINFRA-PROTOCOL.md) preserves the
same twelve inspected bugs, three formats and verifier in a separately identified
bank. Its new $0.08 sublimit stays within the existing $0.60 total ceiling and
carries all prior commitments once. It changes provider and sampling seed;
observations cannot be pooled or interpreted as a controlled provider comparison.

The follow-up is now [complete and independently reproduced](results/contract-deepinfra-20261026/README.md):
current JSON 0/12, example JSON 1/12, plain Python 0/12 full successes.
None passes the fixed engineering gate. All 36 outcomes and 42 verifier records
are retained; no new uncertain calls. The cumulative commitment is $0.01419331,
including historical reserves. A stronger capability/calibration setting is
needed before collecting matched recovery outcomes or fitting a selector.

A separately bounded [Gemma 3 12B capability calibration](CONTRACT-12B-PROTOCOL.md)
is prepared under the user's instruction to continue research. Its
[funded configuration](CONTRACT-12B-AUTHORIZED.json) declares $0.09 within the
existing $0.60 cumulative ceiling, carrying $0.01419331 once. The same twelve
bugs, three response contracts and fixed gate are retained; 36 fresh initial
attempts are planned. Ten-second dispatch spacing and a new seed are declared
before calls. No 12B outcome or scaling claim exists at preparation time.

The [12B calibration is complete](results/contract-gemma12b-20261026/README.md):
1/12, 1/12 and 0/12 full successes under current JSON, example JSON and Python
text, with both successes on the same bug. All72 saved evaluation records
reproduce, no new uncertain calls, cumulative commitment $0.01760731 including
all historical reserves. Increased artifact validity alone does not establish
useful recovery. The gate remains failed and no selector is trained.

The separately frozen [27B capability control](CONTRACT-27B-PROTOCOL.md) is now
[complete and independently reproduced](results/contract-gemma27b-20261026/README.md):
36/36 outcomes, 34 usable sources and three full successes across only two bugs.
Each format solves one bug, so the unchanged gate still fails. All 72 verifier
records reproduce. New charges are $0.00450984; cumulative commitment is
$0.02211715 including historical reserves. The route uses FP8 rather than the
prior BF16, precluding a pure size-effect interpretation.

A [descriptive three-bank comparison](results/capability-comparison-20261026/README.md)
retains test-level progress and regressions. The 27B fixes more public failures,
but seven of its ten public passes fail evaluator tests. No contract is selected,
no recovery advantage is inferred and no selector is trained. Further semantic
and verifier diagnosis precedes another separately frozen recovery study.
