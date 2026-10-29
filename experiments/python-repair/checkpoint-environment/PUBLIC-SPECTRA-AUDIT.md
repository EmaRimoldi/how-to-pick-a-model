# Can public test coverage provide a more targeted diagnostic?

This is an **offline development feasibility audit**, prepared after the previous
trace experiments and their outcomes were known. It is not a new model study,
a fault-localization accuracy evaluation or a selector-training protocol.
It leaves all closed model collections, reserves and gates unchanged.

## Motivation and relation to prior work

The complete independent trace comparison did not establish a useful
intervention: focused feedback repaired 12/32 cases and focused feedback plus a
trace repaired 8/32. In the subsequent contrastive calibration, both trace arms
repaired 9/24 versus 6/24 for focused feedback, but the gain did not repeat across
draw groups. The latest frozen-region study stopped with 11/32 responses and is
inconclusive. Improving the trace recorder alone cannot establish repair value.

One alternative is to summarize **where passing and failing public executions
differ**, instead of appending more intermediate values. This is established
spectrum-based fault localization (SBFL), not a proposed novelty.
[FuseFL (SANER 2024)](https://arxiv.org/html/2403.10507v1) combines suspicious-line
rankings, test outcomes and code descriptions for LLM fault localization. Its
Section II-A gives the Ochiai formula used here; Section III discusses its
Python coverage input. That study does not establish repair gains on our tasks.

For each observed source line, let `ef` and `ep` be the number of failing and
passing public cases executing it, and `F` the total number of failing cases:

`Ochiai = ef / sqrt(F * (ef + ep))`.

We order exact rational squared scores and retain **all tied lines**. We do not
break ties using reference fixes or pretend that a score is a fault probability.
Lines executed only by passing tests receive zero. Unexecuted lines are outside
the ranking; absent code and missing behavior can therefore escape it.

## Fixed scope and information boundary

All eight original buggy adapters from the already-published acquisition
preparation are retained, each with its six public cases. This denominator was
recorded with runtime hashes in `plan.json` before local execution. These are
**original bugs**, not model-generated failed repair checkpoints, and they are
already exposed development data. No unseen bug was inspected. Scores cannot
substitute for evaluation at the final goal's failure checkpoints.

The loader checks the historical archive SHA-256, reads only each `public.json`
and `observation.json`, and discards the provenance field containing fixed-source
URLs. No fixed file, private evaluator, fault annotation or old treatment result
is supplied to acquisition or ranking. Public inputs and expectations were
already available to the solver; coverage adds execution information, not a new
test oracle.

For each public case, ordinary execution and coverage execution run in separate
fresh OS sandboxes. Expected values stay in the parent. Stored, fresh ordinary
and covered observations must agree. A mismatched, interrupted, truncated or
invalid case makes the **whole artifact's spectrum unavailable**; it does not
shrink the denominator. Candidate import happens before instrumentation;
candidate line events during the single-threaded entrypoint call are included,
including runtime imports of the other supplied module. Other threads, module
initialization, external library internals, data dependencies and sub-line
branches are outside this diagnostic's contract. The tracer is not a security
boundary against actively adversarial code; the existing OS sandbox remains the
execution boundary and candidate output never supplies a pass flag.

The new coverage-only worker records up to 100,000 line events and 4,096 distinct
locations. Existing sampled traces are deliberately not interpreted as full
coverage. CPU, output, file and wall-time bounds use the existing verifier.

## Findings and decision

The [saved audit](results/public-spectra-20261029/REPORT.md) contains complete
public spectra for **8/8 artifacts**, with all 48 stored/ordinary/covered
observations agreeing. **7/8** have more than one positive score, so coverage can
distinguish some lines reached by failing tests. For `thefuck-029`, all seven
failing-executed lines tie: this representation provides no ranking among them.
The top-score group contains 1–9 lines on the other seven artifacts. Those lines
may be symptoms or unrelated branches; **no fault-location correctness was
measured**.

The audit consumed 96 local executions plus one sandbox preflight, about 4.71
seconds for acquisition on this machine, and **zero model requests**. All six
public cases are acquired for each artifact, so this costs more executions than
the prior single-failure trace. A future comparison must charge that acquisition
and its prompt length, even if the diagnostic was cached during research.

This supports keeping SBFL as a candidate diagnostic, not starting a selector or
claiming a positive research result. It does not identify the cause of the
previous trace failures. Before any new collection, a separate reviewed protocol
must specify the actual failed-checkpoint population, solver/endpoint, matched
feedback-only control, whole-tie rendering/fallback, repeated draws, complete
repair and regression outcomes, and a common total resource envelope. Static
always-acquire and never-acquire policies remain mandatory comparators. Only a
repeatable repair benefit can justify a subsequent prospective selector on
untouched grouped bugs. The unresolved provider 429 and uncertain reserves remain
separate operational constraints; this audit does not authorize a retry or a
successor to a closed collection.

## Reproduce without credentials

```bash
uv run python scripts/audit_repair_spectra.py replay \
  --output experiments/python-repair/checkpoint-environment/results/public-spectra-20261029
```

Replay checks every artifact hash and the source public projections, then
recalculates all counts, exact ties and the report from saved coverage. It does
not execute candidate code. Frozen inert runtime sources are included. For a
separate local execution replicate on supported macOS, use `collect --output`
with a **new empty destination**; timing and platform-dependent execution are
not guaranteed identical. No command in this audit contacts a model provider.

## Extension to actual generated failures (2026-10-29)

The [second audit](results/generated-spectra-20261029/REPORT.md) uses the frozen
Gemma 3 27B `json_current` output bank, which also supplied the earlier diagnostic
experiments. All twelve source candidates remain in provenance. The historical
public-only trigger selects eight failed artifacts; four pass the public suite
and receive no diagnostic acquisition. **A public pass is not a full-repair
label.** Private evaluator outcomes were not used for selection or scoring.

The loader verifies the complete original archive, projects only public task,
generated artifact and public observation fields, and omits fixed-source
provenance and private outcomes. The selected IDs and all twelve eligibility
records were frozen before executing the unchanged coverage worker. This is
post hoc development feasibility on already-exposed cases, not fresh evidence
of repair benefit or an alteration of the closed source bank.

All 48 selected public cases reproduce across saved, ordinary and covered
execution. Seven failed checkpoints produce multiple positive scores; the seven
failing-executed lines of `youtube-dl-020` remain tied. Top-score groups on the
other seven contain 1–9 lines. A separate direct-formula calculation agrees on
all **130** covered-line scores. Acquisition used 96 executions plus one
preflight, about 7.39 seconds on this machine, and no model calls.

This removes the restriction that feasibility was tested only on original code:
the representation can also be produced at actual model-failure checkpoints.
It does **not** show that the selected lines are faulty, that repairs improve,
or that the diagnostic pays for itself. Seven selected bugs are from youtube-dl
and one from HTTPie; six have only one public failing case. Such a narrow,
previously exposed development population cannot support a generalization claim.
Do not compare the two audits causally: their bugs and source states differ.
The next necessary evidence is the separately specified matched model experiment,
not more coverage engineering or selector fitting.

```bash
uv run python scripts/audit_repair_spectra.py replay \
  --output experiments/python-repair/checkpoint-environment/results/generated-spectra-20261029
```

Both archives remain independently replayable. A fresh local execution replicate
of the generated source uses `collect --bank generated --output <new-directory>`;
it still makes no provider requests.
