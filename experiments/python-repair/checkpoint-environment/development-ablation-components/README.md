# Five bounded development components; broader environment still needed

The complete prospective [34-ID source queue](../results/spectrum-ablation-preparation-20261030/source-plan.json)
has now been read at patch level. Its [feasibility review](../results/spectrum-ablation-preparation-20261030/feasibility-review.json)
retains every ID in original order, records the required environment and provisional
function family, and identifies these five components for bounded qualification.
These are **not a final scientific cohort or five qualified full upstream bugs**.
The remaining 29 IDs require package, parser, filesystem, lifecycle or tracing
context; they are deferred to a broader environment, not discarded as failures.

## Qualification result

All five components have a repeatable original failure and a reference that
passes both disjoint input suites. Each artifact/suite is executed twice in a
fresh native macOS sandbox: **40 suites and 256 candidate-case executions**, plus
five sandbox preflights. No model calls or paid collection occurred. Full suite
observations, event chains, timing and the exact executed runtime are preserved
in `qualification-evidence.zip`; `qualification.json` contains the full report.

| Source component | Initial public passes | Initial evaluator passes | Reference public / evaluator |
| --- | ---: | ---: | ---: |
| tqdm/2: ANSI trimming and width helpers | 4/6 | 4/6 | 6/6, 6/6 |
| tqdm/4: progress meter with numeric scaling | 3/6 | 3/6 | 6/6, 6/6 |
| black/17: source-byte decoding | 5/6 | 5/6 | 6/6, 6/6 |
| tqdm/8: custom progress-bar formatting | 2/6 | 2/6 | 6/6, 6/6 |
| tqdm/9: SI-prefix rounding | 4/8 | 3/8 | 8/8, 8/8 |

The pool, all test inputs/expectations and selection order were hashed in
[qualification-plan.json](qualification-plan.json) **before execution**. No cases,
reference outputs, wrappers or criteria changed after observing results. Expected
values were specified from the public behavior and upstream regression examples,
not collected by executing the fixed implementation to create an oracle. The
default reproducer independently rescores every saved observation and requires
both repetitions, with no missing or extra artifact/suite/case.

## Source fidelity and limits

`upstream-sources.zip` retains 21 pinned full source/test/license files as inert
text. Every used function body and dependency block is extracted byte for byte
at recorded line ranges. Source digests, complete licenses and original commit
URLs are in [pool.json](pool.json). `audit_sources` checks all original bytes and
each excerpt. The build script is retained as inert `build-adapters-source.py.txt`.
The first Python downloader failed at transport without obtaining source bytes;
curl downloaded the files. The historical tqdm/9 license was at `LICENSE`, not
`LICENCE`; the 404, corrected path and all download records remain in the archive.

Both versions receive the **same** JSON wrapper and prefix. The progress-meter
adapters retain original static methods/decorators in a minimal `tqdm` class;
the methods do not access the omitted instance lifecycle. Python 3 `chr`/`str`
aliases replace compatibility imports, and `RE_ANSI` is the upstream expression.
Black's byte adapter converts a JSON hex string to bytes and returns the actual
`decode_bytes` tuple. No behavioral mock, reconstructed buggy function or
reference-specific wrapper is used. Qualification uses the recorded current
Python runtime, not BugsInPy's historical Python 3.6/3.8 environments.

Three upstream patches have deliberately narrower component coverage here:

- tqdm/2 also changes `std.format_meter`; this pool tests only `utils.disp_trim`.
- black/17 also changes `lib2to3_parse`; this pool tests only `decode_bytes`.
- tqdm/9 also changes `__len__`; this pool tests only `format_sizeof`.

Even the two complete target-method changes are function-level adaptations,
not official full-project BugsInPy scores. Tests are finite and cannot certify
semantic correctness, model difficulty, useful intermediate repairs or useful
diagnostic information. All inputs, evaluators and reference patches are
published development material, and original bugs are not model-generated
failed-repair checkpoints.

The five IDs span only **two projects**. tqdm/4 and tqdm/8 share `format_meter`;
their size-formatting helper also overlaps the target in tqdm/9. A conservative
function-family analysis must cluster those three together. The ANSI utility
is a separate function family in the same project; black/17 overlaps the encoding
family of the reviewed black/18 and black/21. This is at most three provisional
component families, not five independent observations. Historical alias/family
audits remain necessary for any future split. The exposure registry retains
208 IDs and adds the published-adapter evidence without changing any holdout.

## Consequence for the research design

The present bounded environment cannot supply a credible new-bug experiment by
declaring these five components the whole population. **No F/N/S model cohort,
effect threshold, sample size or new budget is frozen here.** The next work is
to support faithful package/context execution for the deferred cases, beginning
with the original tokenizer/driver interfaces rather than fake parse-tree inputs,
and to record a broader prospective source/split plan before opening untouched
project contents. More draws on these few components would not create independent
bugs or satisfy the selector goal. The closed spectrum screen remains unchanged.

## Reproduce

From the repository root, offline and without executing upstream code:

```bash
uv run python experiments/python-repair/checkpoint-environment/development-ablation-components/reproduce.py
uv run python scripts/audit_repair_exposure.py
```

To independently execute the five components again, requiring macOS sandbox-exec:

```bash
uv run python experiments/python-repair/checkpoint-environment/development-ablation-components/reproduce.py --sandbox
```

The latter compares every repeated output to the saved bank, excluding only
variable timing. It uses temporary paths and never changes the closed evidence,
starts a model collection or releases any historical uncertain reservation.
