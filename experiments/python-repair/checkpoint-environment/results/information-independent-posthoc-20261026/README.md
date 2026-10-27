# Post hoc audit of the complete trace bank

The failed primary screen is unchanged: **12/32 focused-feedback versus 8/32
trace-assisted full repairs**. This audit inspects all 64 responses and all twelve
source candidates, including four untriggered sources. It follows the recorded
[audit plan](audit-plan.json), written after the primary result was known.
It makes no model calls, trains no selector, and cannot identify a causal mechanism.

## What the evidence rules out and leaves open

All eight eligible source traces are available, agree with ordinary execution,
and retain an entrypoint return event. Return events also occur during exception
unwinding: the timestamp case raises `ValueError`, rather than returning `None`.
Seven traces drop no events; httpie's trace retains the last 32 of 51. None hits
the 512-event capture ceiling. Widespread trace truncation is therefore not an
observed explanation for this bank's failed screen.

| Source bug | Public failures | Traced case | Retained / seen | Dropped |
| --- | --- | --- | ---: | ---: |
| youtube-dl-003 | stray-before-quote | stray-before-quote | 17/17 | 0 |
| youtube-dl-013 | rtmp-no-base | rtmp-no-base | 10/10 | 0 |
| youtube-dl-020 | boolean-before | boolean-before | 12/12 | 0 |
| youtube-dl-031 | minutes | minutes | 15/15 | 0 |
| youtube-dl-033 | fraction-z | fraction-z | 22/22 | 0 |
| youtube-dl-042 | existing, raw | existing | 10/10 | 0 |
| youtube-dl-043 | deep | deep | 6/6 | 0 |
| httpie-005 | long-escape, escaped-colon | long-escape | 32/51 | 19 |

Six traces contain value-omission markers. Several omitted local slots are used
for regular-expression matches in the source, but their actual runtime type and
contents cannot be recovered from the saved marker alone. The current safe
observer deliberately excludes arbitrary object inspection. This is a concrete
information limit, not evidence that exposing those objects would improve repair.

The earlier copying diagnosis does not dominate this Qwen bank: 59 outputs make
parseable syntax changes beyond the entrypoint, two are exact copies, two contain
Python syntax errors and one has no valid artifact. Syntax change is not semantic
correctness. There are 57 distinct parseable ASTs across both arms.

## Progress is often incomplete

| Response-level outcome | Focused | Focused + trace |
| --- | ---: | ---: |
| Corrects at least one initially failing public test | 20 | 19 |
| Corrects the selected first failure | 16 | 15 |
| Regresses at least one initially passing public test | 6 | 8 |
| Both corrects a failure and regresses a pass | 0 | 3 |
| Passes all public tests | 14 | 10 |
| Passes public but fails evaluator tests | 2 | 2 |
| Full repair | 12 | 8 |
| No executable artifact / unmeasured transitions | 0 | 1 |

These overlapping counts retain all observations; they are not independent bug
samples. The new regression definition is **any previously passing case that
fails**, whereas the primary report uses a **net public-score decrease** (6 per
arm). A repair can fix one case and break another without lowering its net score.
The missing artifact is an observed unsuccessful response, but has no measured
test transitions. Two Python load errors and seven responses with failed runtime
exceptions remain in the case-level record.

On youtube-dl-042, six outputs fix the first failure but none fixes the second
public failure. On httpie-005, all eight outputs fix the second public failure
but none fixes the first. A single corrected example is inadequate as the repair
objective. On youtube-dl-020, three trace responses contain invalid regex patterns;
another focused response fails string formatting at runtime. These statements
describe the saved candidates, not why the model generated them.

## Public false acceptances: manual artifact inspection

All four were inspected, alongside every case-level outcome in [audit.json](audit.json).
These are post hoc evaluator findings and must never become deployable prompt data.

| Bug / arm / draw | Observed patch behavior | Requirement already in the public instruction |
| --- | --- | --- |
| 013 / focused / 0 | Limits absolute paths to HTTP(S) and RTMP | Any valid scheme followed by `//` must be preserved |
| 013 / focused_trace / 1 | Requires a base for scheme-relative paths | A scheme-relative path must be returned unchanged even without a valid base |
| 033 / focused_trace / 2 | Removes the fractional suffix together with its timezone | Discard fractional seconds while respecting signed timezone offsets |
| 043 / focused / 0 | Accepts arbitrary URL schemes | Only HTTP, HTTPS and scheme-relative inputs are supported |

This supports auditing preservation and acceptance coverage separately from
local failure repair. It does not show that traces cause overfitting or that
another diagnostic can correct these weaknesses.

## Next falsifiable intervention

The [separate offline preparation](../contrastive-preparation-20261026/README.md)
compares a failing execution with an already-passing public execution and preserves
all existing tests and feedback. Its purpose is to expose behavior to preserve,
while a single-trace control separates the added contrast from representation.
No model efficacy result exists for it. Value omissions remain visible; no hidden
oracle or reference-derived value is added. The [design](../../CONTRASTIVE-DIAGNOSTIC-DESIGN.md)
states controls, related work and remaining prerequisites.

## Reproduce

```bash
uv run python scripts/audit_repair_trace_information.py \
  --input experiments/python-repair/checkpoint-environment/results/information-independent-20261026 \
  --output runs/fresh-trace-posthoc-audit.json
```

The script verifies the original archive/member/object hashes and terminal state,
then inspects inert data; it never executes model candidates. Output should equal
the published `audit.json`. The original evidence archive is
`0c84d4fd10ce06b971b75340e7cb522c77410d278f439fcf1078680bb876377b`.
Historical primary analyses, intervals, budgets and failed gates are unchanged.
