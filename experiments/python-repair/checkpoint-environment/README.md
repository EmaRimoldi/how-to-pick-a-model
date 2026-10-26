# Python repair checkpoint environment

**Status: executable offline engineering prototype. No model responses, real-bug
benchmark results, paid collector, fitted selector or frozen scientific evaluation.**

The domain is function-level Python repair: one or two flat, standard-library
modules, a named callable and JSON inputs/outputs. The environment saves complete
artifacts, public verification, progress histories and branch ancestry. It restores
earlier artifacts without changing saved checkpoints.

The first question is whether public progress history predicts the benefit of
keeping a failed patch rather than restoring the original buggy code. The
finite-expression prototype in [PR 14](https://github.com/EmaRimoldi/how-to-pick-a-model/pull/14)
remains a separate, unmerged design. This implementation starts from current main;
completed HumanEval+, MBPP+ and BigCodeBench studies are unchanged.

## Run locally

Use the normal environment (`uv sync --dev --frozen`). Planning and saved-run
audits are portable. Candidate execution requires macOS `sandbox-exec`, as in the
existing verifier. There is no unrestricted fallback or provider-backed mode.

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

[BugsInPy](https://github.com/soarsmu/BugsInPy) is a candidate source, not an
implemented full-repository importer. For an adapted function-level task, record
the upstream bug ID, repository URL, buggy/fixed commits, source hashes, license,
runtime requirements and every extraction/change in provenance. Preserve original
sources locally. Reject tasks whose dependencies or semantics cannot be reproduced
with this standard-library contract. Report adapted tasks as adapted tasks, not
official BugsInPy scores. Never manufacture LLM progress from a reference fix.

Select a development pool on technical criteria before model outcomes. Calibrate
Gemma 3 4B there to establish natural recoverable failures. Every inspected case
remains development data. A model pilot needs a new authorized budget, provider
settings, collector implementation and protocol freeze; historical ceilings do
not authorize new spending.

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
