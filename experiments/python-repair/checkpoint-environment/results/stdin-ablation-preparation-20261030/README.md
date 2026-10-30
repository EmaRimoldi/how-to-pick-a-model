# Whole-program F/N/S preparation: two complete offline banks

All eleven source-qualified FixEval development groups now have reproducible,
public-only feedback (F), neutral source excerpts (N), and the same excerpts with
test-association scores (S). No model was called and no repair benefit was measured.
All twelve original group decisions remain in provenance; the excluded group is
not silently replaced. See the [source qualification](../fixeval-source-qualification-20261030/README.md).

The first instrumentation bank hit repeated-event/CPU limits on loops. It is
preserved unchanged. A separately recorded engineering comparison used CPython
3.13.12 monitoring to disable a line callback after its first location hit, while
retaining the line-presence union. This follows the documented
[LINE and DISABLE semantics](https://docs.python.org/3.13/library/sys.monitoring.html).
The old backend and its frozen evidence remain unchanged; the new coverage schema
has a distinct version. Neither captures execution frequencies.

| Diagnostic outcome | Legacy tracing | Monitoring |
| --- | ---: | ---: |
| Different scores among covered lines | 3 | 4 |
| Complete but flat scores | 3 | 5 |
| Complete empty coverage | 1 | 1 |
| Unavailable | 4 | 1 |
| Total groups | 11 | 11 |

Across banks, all **82 ordinary observations agree**. Within the monitoring bank,
all **82 covered/ordinary observations agree**. The **60 complete legacy captures**
have the same line sets under monitoring. Checks compare status, return code,
stdout and normalized stderr, retaining raw bytes in evidence. All 66 F/N/S
requests reproduce, and a separate raw-IO/Fraction calculation verifies every
available diagnostic score. N and S share exactly the same excerpts and order;
withheld fields are marked explicitly, not replaced by zero. They are not
token-length matched. Evaluator tests, reference code and provenance are absent
from every request.

Each bank used 82 fresh observations plus 164 acquisition executions and two
isolation preflight probes. Recorded total wall times were 50.42 and 40.16 seconds,
including their respective preflights. These single engineering runs do not
estimate a general speedup. Per-case elapsed times and projection costs are
retained. Independent native replay is a separate execution cost, not part of
either original bank's recorded wall time.
The [independent native replay](native-replay.txt) completed all **492 case
executions plus four preflight probes with zero discrepancies**, without model calls.

`p03307` remains unavailable because some ordinary executions themselves exhaust
the CPU limit. `p03207` has a Python syntax error and empty coverage. Five other
programs have flat scores. All remain selected: diagnostic availability or apparent
informativeness cannot select the future model cohort. Differentiated scores do
not establish correct fault localization, useful repairs or selector feasibility.
These are human failed submissions on already inspected development tasks, not
generated failed repairs or untouched evaluation bugs. The full goal remains open.

## Reproduce

From the repository root:

```bash
uv run python experiments/python-repair/checkpoint-environment/results/stdin-ablation-preparation-20261030/reproduce.py
```

This verifies the archive/member hashes, frozen implementations, all source/test
bindings against the original qualification, phase journals, resource totals,
public-score calculations, 66 inert requests and the entire [analysis](analysis.json).
Archived source remains `.txt` data. No candidate code or network call executes.

Add `--reexecute` on the exact frozen CPython 3.13.12 macOS environment to rerun
all 492 case executions plus four preflight probes in the native sandbox. The
replay checks complete observations and coverage, not timing equality. It never
calls a model. Filesystem, networking and credential isolation remain enforced.

[evidence.zip](evidence.zip) contains both complete banks, the comparison plan
written before the monitoring run, and exact frozen implementation bytes.
[manifest.json](manifest.json) binds every member. No published historical bank
was resumed or rewritten. Next: a separately frozen initial-failure/recovery
pilot, with numerical criteria and a declared allocation, before any model call.

## Numerical pilot design

The [prospective protocol](../../STDIN-PILOT-PROTOCOL.md) and
[reproducible design](pilot-design.json) fix a proposed eleven-initial-call,
three-arm/three-draw screen on generated public-failure checkpoints. Maximum
110 calls reserve $0.31088640 with the recorded Gemma 3 4B Parasail prices; the
proposed $0.32 suballocation fits the existing cumulative $0.60 ceiling, including
the $0.25463059 historical commitment. It is not yet an executable funded freeze.
The collector and receipt/projection audit remain required before launch.

All 33 currently observed human-state prompts fit the conservative admission
bound (maximum 19436 bytes plus framing as counted by that rule). All 72 original
human source artifacts fit the strict JSON output contract; the largest canonical
JSON is 1032 UTF-8 bytes. These are not exact Gemma token counts or a guarantee
about future generated checkpoints. The initial-repair stage must demonstrate
materializable failures and repair capacity; no source/state substitutions are
allowed to make the screen succeed.

The tested analysis uses S−N as primary, retains S−F as a safety comparison, and
cannot advance on incomplete banks, a failed draw, or fewer than six generated
failure checkpoints. Success only permits independent replication planning,
never selector training. Eleven groups do not provide a powered population claim.
The design records numerical granularity, not a simulated power guarantee.

```bash
uv run python scripts/prepare_stdin_pilot.py --check
uv run python -m pytest -q tests/decisions/test_stdin_pilot.py
```

The [endpoint snapshot](gemma-endpoints-observation.json) is public metadata, not
proof that requests will succeed; it must be checked again at the live freeze.
