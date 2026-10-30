# Three-arm ablation preparation: code ready, new cohort not yet qualified

The user activated the new selector goal on 2026-10-30. This preparation implements
the next controlled comparison and begins a prospectively ordered new-source
screen. It is **not a model result or a launch authorization**. No API/model calls,
candidate executions or new spending occurred here. The old spectrum screen and
its failed repeatability criterion remain unchanged.

## Implemented intervention boundary

`vao.repair.spectrum_ablation` constructs three inert requests from current public
files, instruction, test cases, feedback and a bound public-coverage acquisition:

| Arm | Additional information |
| --- | --- |
| feedback (F) | None. |
| neutral (N) | Every covered source location and source text in filename/line order; all outcome-association fields say `not supplied`. |
| scored (S) | Identical locations, text and order, with true passing/failing execution counts and exact squared Ochiai scores. |

The system prompt is identical across arms. No top-k, rank ordering, hidden
evaluator, reference fix, task ID, provenance URL, timing metadata or cached
diagnostic summary enters the projection. Scores are recomputed from the public
execution observations. A changed/stale binding, missing feedback case or
inconsistent pass label is rejected. Incomplete coverage is represented as a
whole unavailable acquisition in both N/S, without removing the task. Flat ties
and zero scores are retained. Both N and S require coverage; N is not a free
deployable intervention. Placeholder length is not token matching.

Thirteen targeted tests include outcome-association erasure, common-input
identity, canonical ordering, zero/tied scores, metadata poisoning, stale
observations, invalid acquisition and a public-pass recovery guard. Twenty-four
inert requests reproduce on **eight old, already-exposed checkpoints** in
[projections.json](projections.json). Those inputs test software invariants only:
they are not the new cohort and supply no treatment outcomes to this study.

## New-source queue and exposure

The [source plan](source-plan.json) was saved before fetching any candidate bug
metadata/patch. It uses the existing pinned [BugsInPy revision](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd),
the complete catalog of 501 normalized IDs, and a frozen copy of the prior
174-ID development-exposure registry. It takes **all 34 previously unlisted IDs
inside already-exposed projects**, ordered by a fixed SHA-256 key:

| Project | Candidate IDs |
| --- | ---: |
| black | 22 |
| tqdm | 8 |
| cookiecutter | 2 |
| PySnooper | 2 |

Case normalization matters: `PySnooper/1` is already exposed and is excluded.
The other seven project groups (293 IDs in the catalog) have not had their bug
contents opened by this preparation. Their identifiers are not a certified
holdout or a final split. Before independent evaluation, all prior source,
function-family and project exposure must still be checked.

All 72 planned metadata/patch/project records were retrieved as inert text and
verified against their pinned Git blob hashes. All 34 patch headers and metadata
are in [source-screen.json](source-screen.json); all bytes are retained in
`source-screen.zip`. No upstream setup/test script was executed. No candidate
has yet passed adapter, dependency, specification or verifier qualification.
The first four patches were also read in detail (cookiecutter/2, black/13,
cookiecutter/4, tqdm/2); no task was selected from those readings. They involve
filesystem hook discovery/execution, tokenizer state, exception propagation and
display-width handling respectively, so a one-function adapter cannot be assumed
to preserve the complete upstream fix.

All 34 IDs are now **development-exposed**, bringing the current documented
registry to **208 IDs across ten projects**. This update prevents their later
relabeling as untouched evaluation. The frozen old registry remains in
`catalog-inputs.zip` so the original queue is reproducible after the registry
changes. Duplicate function/patch families require grouping before choosing
analysis units; 34 IDs do not establish 34 independent bugs. Prior absence in
our registry does not certify absence of pretraining or undocumented exposure.

## What sample size and resources still require

[planning.json](planning.json) provides a sensitivity calculation, not a power
guarantee or a selected sample size. For illustration, with three draws per arm,
a hypothetical paired discordance of 0.4 and within-bug correlation of 0.5, the
normal approximation gives these independent-bug requirements for two-sided
alpha 0.05 and nominal 80% power:

| Mean improvement to detect | Approximate independent bugs |
| --- | ---: |
| 5 percentage points | 832 |
| 10 percentage points | 205 |
| 15 percentage points | 88 |

The full table varies discordance and within-bug correlation. Assumptions are
not fitted to the eight historical bugs. Project/function clustering, public
trigger yield, verifier gaps, finite-sample behavior and joint advancement gates
are not covered by this approximation. **The current 34-ID queue cannot be
called a powered confirmatory study from these calculations.** Qualification
and a broader source strategy may be necessary; more draws on a few bugs do
not create more independent bug groups. Do not relax the effect criterion to
fit a convenient cohort after observing treatment outcomes.

A provisional one-initial-attempt plus three-arms-by-three-draws design would
require at most 340 requests if all 34 candidates qualify and trigger. With
the *historical* model price assumptions and conservative token reservation,
that reserves **$2.45104640**. This is not a live price quote or an allocation.
Current cumulative commitment remains **$0.25463059 / $0.60**, leaving
**$0.34536941** within the existing ceiling, with all fourteen old uncertain
reservations still included. The entire provisional design does not fit that
ceiling. No partial prefix collection is started in anticipation of another
budget. A concrete qualified cohort, final numerical design, exact requests,
price verification and declared authorized resources must precede dispatch.

## Next work and route to the goal

Qualify the complete 34-candidate queue in its recorded order. Keep every
exclusion with a technical reason, audit shared upstream functions, obtain
licenses and pinned source/test bytes, and verify original bug/fix behavior in
isolation. Do not replace hard or uninformative cases based on model outcomes.
If faithful adapters or independent groups are insufficient, broaden the
environment/source strategy under a separately recorded prospective selection
plan while protecting independent evaluation groups. Preserve the current
scope limitation instead of manufacturing simple substitutes for real bugs.

Then freeze a numerical cohort/draw design, estimand, missing-data rule,
minimum useful effect and uncertainty procedure **before any model result**.
The primary remains S minus N; F is an indispensable usefulness reference, not
a secondary comparison chosen only when favorable. Repeat a useful intervention
on independent groups before an equal-total-resource policy comparison. Only
then fit the pre-acquisition selector on development data and evaluate it on
untouched groups against the best development-selected fixed strategy.

## Reproduction

From the repository root, without network, model calls or candidate execution:

```bash
uv run python scripts/prepare_spectrum_ablation.py --output experiments/python-repair/checkpoint-environment/results/spectrum-ablation-preparation-20261030/projections.json --check
uv run python experiments/python-repair/checkpoint-environment/results/spectrum-ablation-preparation-20261030/reproduce.py
uv run python scripts/audit_repair_exposure.py
uv run pytest tests/decisions/test_spectrum_ablation.py tests/decisions/test_repair_exposure.py -q
```

The preparation reproducer checks the immutable catalog boundary, all 72 pinned
Git objects, every queue identity, derived source summaries, numerical planning
and the 24 public-only projections. It does not certify a qualified task pool,
an effective intervention or the final selector. The full research goal remains
active and unfinished.
