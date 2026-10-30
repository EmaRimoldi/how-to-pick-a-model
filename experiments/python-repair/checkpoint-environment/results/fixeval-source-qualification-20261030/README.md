# Qualification of the frozen FixEval development queue

**25 of 36 human submission pairs meet the offline qualification rule, providing
11 usable development problems from the 12 originally selected groups.** This is
environment evidence, not model recovery or diagnostic efficacy. No model calls
were made; cumulative API commitment stays $0.25463059 / $0.60 with fourteen
historical uncertain reserves. All 36 pairs, all exclusions and the unqualified
problem remain in the artifact.

## Source and execution

The [prospective queue](../fixeval-source-access-20261030/README.md) fixed IDs before
candidate/test inspection. The full original CodeNet archive was cached as opaque
data, with its prior ETag and exact 8,343,137,473-byte size. Streaming its 14,028,302
headers opened only 72 selected programs and 12 selected statements: 84 files,
46,248 bytes, no missing or rejected members. Other archive member bodies were
skipped without agent inspection. The full cache stays outside Git; its SHA256
and all selected byte hashes are retained.

For the 173 selected test pairs, the original remote central-directory identity
was rechecked. Bounded group ranges retrieved 346 input/output files, checking
each local ZIP header, compressed size, decompression limit, CRC32 and byte length.
Source and test retrieval plans/receipts, original bytes and the subsequent
qualification freeze are in `evidence.zip`; all program bodies and archived
scripts are inert text. No tokenization, source rewrite, input stripping, Python 2
fallback or reference repair was applied.

The frozen rule requires the accepted program to pass every test in two repetitions,
and the buggy program to fail at least one public and one evaluator case in both.
Per-case pass and stdout must remain stable. All three ordered pairs per problem
are evaluated; at most the first eligible pair is retained for later development.
This is qualification on human submissions, **not an actual model-generated
failed-repair cohort**.

Every problem requires integer or literal Yes/No output. Two statements explicitly
reject float-formatted integers. Scoring compares ASCII-whitespace-separated bytes
without numeric coercion and requires a successful exit. The parent sees expected
answers; the sandbox receives only original program bytes and one unchanged input.
All cases run in fresh native sandboxes with the [whole-program backend](../../STDIN-ENVIRONMENT.md).

Public/evaluator assignment is fixed before execution, grouping identical
ASCII-tokenized inputs together without altering the executed bytes. All statement
sample inputs are public; other groups are deterministically ordered by the frozen
seed, with at least half assigned public and at least two distinct input groups
required in each split. There are no partition conflicts or sample inputs in the
evaluator. These within-problem tests are not independent held-out problem groups.

## Runtime deviation

The parameter prose incorrectly named **CPython 3.11**. The full pre-execution
manifest instead recorded the actual **CPython 3.13.12**, its executable hash and
all implementation hashes, and the collector enforced those exact identities.
The unchanged prose and exact manifest are both preserved. These results qualify
the recorded 3.13.12 environment only; no 3.11 or historical 3.4/3.8 replay is
claimed. CI's Python 3.11 run audits saved evidence and portable tests, not native
candidate execution. This recording deviation is not hidden by editing the freeze.

One reference (p03307, pair 2) calls `fractions.gcd`, unavailable in the executed
interpreter; it fails all twelve cases in both repetitions. It stays excluded.
Neither the reference nor the environment was patched to rescue its result.

## Complete results

| Problem | Public / evaluator cases | Eligible pairs / 3 | Retained pair index |
| --- | ---: | ---: | ---: |
| p02621 | 5 / 5 | 3 | 0 |
| p03307 | 6 / 6 | 2 | 0 |
| p02633 | 6 / 5 | 3 | 0 |
| p03126 | 8 / 7 | 3 | 0 |
| p02570 | 8 / 8 | 3 | 0 |
| p02700 | 6 / 6 | 2 | 0 |
| p03032 | 12 / 11 | 2 | 1 |
| p03296 | 7 / 6 | 0 | None |
| p03329 | 10 / 9 | 1 | 0 |
| p02987 | 6 / 6 | 2 | 0 |
| p03806 | 10 / 10 | 2 | 1 |
| p03207 | 5 / 5 | 2 | 1 |

There are 2,076 candidate-case executions plus two isolation preflight executions.
All candidates exit within the wall/output bounds; nonzero program exits remain
test failures. Independent rescoring agrees on every saved observation. The
qualification excludes one pair for reference failure, three because the buggy
program passes all public cases and seven because it passes all evaluator cases.
All three p03296 pairs fall into the latter category; the problem is not replaced.
No repeat-instability exclusion occurs. Raw errors and every case remain available.

Recorded case execution time totals 273.03 seconds; wall time including preflight
and collector overhead is 275.73 seconds. Retrieval, metadata screening, engineering
tests and later re-execution are separate preparation costs, not included in these
figures. These measurements do not establish equal total resources for a policy.

## Reproduce

From the repository root, the default audit verifies all archive hashes, original
source/test projections and frozen implementation bytes, checks sample/partition
separation, independently scores all 2,076 cases and reapplies every qualification
rule. It does not execute dataset code or access the network:

```sh
uv run python experiments/python-repair/checkpoint-environment/results/fixeval-source-qualification-20261030/reproduce.py
```

An explicit native replay reruns all 2,076 cases with the exact recorded Python
binary and backend, checking stdout, status, exit code and pass flags. It refuses
a changed runtime or implementation; a different environment is a separate
compatibility study. It makes no model calls:

```sh
uv run python experiments/python-repair/checkpoint-environment/results/fixeval-source-qualification-20261030/reproduce.py --reexecute
```

The separate native replay completed all **2,076 executions with zero
discrepancies**; `native-replay.txt` retains its terminal receipt. These extra
executions are validation overhead, separate from the original qualification
timings above. Default CI performs the inert audit, not native replay.

## Scope and next step

These are real human competitive-programming submissions, including several very
simple tasks and some dynamic-programming tasks. Qualification does not establish
that the models will fail, that there will be enough recovery checkpoints, that
diagnostics help, or that a selector generalizes to repository maintenance. The
68 other eligible groups remain unopened by the agent and are not yet certified
independent data. Original BugsInPy and closed model-study evidence is preserved.

Next prepare matched F/N/S projections for this whole-program interface, verify
public-only diagnostic acquisition and token capacity, then freeze the complete
model protocol and authorized resource envelope. Initial model successes must
remain in the denominator; only actual public-failing model artifacts can enter
the recovery study. Insufficient failures are a possible study outcome, not
permission to replace tasks or manufacture failures after collection starts.

CodeNet-derived programs/statements carry the included CDLA-Permissive 2.0 text.
Test files and metadata originate from the FixEval authors' public data archive,
with the upstream MIT notice retained. The pinned sources, exact author download
identifiers and directory fingerprints are recorded in the preceding access
artifact; no credentials or signed download links are included here.
