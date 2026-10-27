# Broader development cases for failure-coverage diagnostics

Six additional adapted BugsInPy cases across four previously inspected projects
pass offline qualification: every buggy version fails both suites, and every
original fix passes both suites twice. These are **development engineering
results, with zero model calls**. They establish neither model difficulty nor
diagnostic benefit. No evaluation holdout was consumed or selected.

| Source bug | Restricted repair surface | Public failures in buggy version |
| --- | --- | ---: |
| scrapy/2 | Optional-capacity insertion-order cache | 2/6 |
| scrapy/36 | Factory dispatch and rejection of invalid construction | 3/6 |
| luigi/10 | Pending/running task ownership across workers | 2/6 |
| tornado/5 | Deadline arithmetic after overruns or backward clock movement | 2/6 |
| thefuck/22 | Empty lazy command sequences and preserved ordering | 2/6 |
| thefuck/29 | Nonmutating defaults merge that preserves configured values | 4/6 |

These are two to four failing **test cases** per bug, not that many independent
defects. Several cases exercise different inputs of the same underlying fault.

The [screening record](screening.json) retains all nine considered candidates;
three were deferred because of broader subsystem/adapter dependencies. These IDs
were already development-exposed through the original header screen. Selection
preceded all model calls, but remains purposive rather than representative.
The [exposure registry](../development/exposure-registry.json) now records these
published adapters; its known totals remain 174 IDs and ten projects.

## Provenance and limits

[pool.json](pool.json) records pinned commits, full-file hashes, exact extraction
ranges, instructions, wrappers, public cases and evaluator cases. The complete
target functions/classes or methods are preserved byte-for-byte in inert text.
[source-audit.json](source-audit.json) verifies 25 source/support/test/license files
against the pinned downloads. Original licenses are retained under `licenses/`.
The source benchmark revision is `11c5f1eea954a42132cfd06bf257766a7963e0fd`.

The scope is explicit: unique cache keys; inert factory classes; worker attribute
containers with the original pending/running-union semantics; timer arithmetic
without an event loop; unique command strings and distinct priorities with no
shell execution; and ordinary settings keys that do not shadow dict methods.
These adapters do not claim full-project BugsInPy performance, LRU semantics,
live scheduling, command side effects or unrelated duplicate-handling behavior.

The 36 public and 36 evaluator inputs are disjoint within each task. Expected
values were authored from the restricted contracts and upstream examples before
qualification, not obtained by running the fixes. Both suites are published
development data, excluded from one another's solver-facing channel rather than
claimed as secret or representative samples.

[qualification-history.json](qualification-history.json) preserves the first
5/6 result. The timer's manually specified numeric timestamps matched the fix,
but canonical JSON distinguished integer and floating encodings. Both buggy and
fixed wrappers now normalize timestamps to float, and the same expected numbers
are explicitly encoded as floats. Inputs, numeric expected values and original
method bodies were unchanged; the historical verifier was not modified.
The final [qualification](qualification.json) repeats all six published adapters
and passes 6/6. Each qualification executes 288 ordinary cases plus isolation
probes; these repeated checks are not independent experimental samples.

## Diagnostic feasibility

The [public-only preparation](coverage/summary.json) compares first-failure and
all-failure traces on the initial buggy artifact. All six sources have multiple
public failures, so coverage differs on every source, unlike six of the eight
earlier checkpoints. Baseline code, all public tests, expected answers and public
feedback remain identical. More traces do not provide new oracle labels.

Both variants acquired matching ordinary/traced observations on all six tasks;
their shared first trace and compact retained-value roundtrips agree exactly.
First-failure acquisition uses 12 sandbox executions across six tasks; all-failure
uses 30. The largest complete message is 19,484 UTF-8 bytes. These counts/timings
are engineering measurements, not provider token counts, paid-call authorization
or an equal-total-resource policy result. Per-task public records are retained
under `coverage/`, including acquisition costs and unavailable-record semantics.

The [candidate design](../FAILURE-COVERAGE-DESIGN.md) sets out the next scientific
question. No selector or live collection is created by this pool.

## Reproduction

From the repository root, with fresh output paths:

```bash
uv run python scripts/qualify_python_repair_pool.py \
  --pool experiments/python-repair/checkpoint-environment/development-broader
uv run python scripts/qualify_python_repair_pool.py qualify \
  --pool experiments/python-repair/checkpoint-environment/development-broader \
  --output runs/broader-pool-qualification
uv run python scripts/prepare_failure_coverage_diagnostics.py \
  --pool experiments/python-repair/checkpoint-environment/development-broader \
  --output runs/broader-coverage-preparation
```

Qualification requires the documented macOS sandbox backend. For source audits,
download each pinned provenance URL as `<cache>/<benchmark_id>/<role>.txt` and use
the existing `audit-sources` action. No upstream setup script is executed. All
commands above are offline and make no model calls.
