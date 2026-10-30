# Post hoc spectrum audit: useful repairs, persistent semantic failures

This is an **offline, retrospective audit of all 48 responses**, not a new model
experiment. The aggregates were known when [the audit plan](audit-plan.json)
was recorded. All eight triggered checkpoints and twelve source candidates are
retained. The original result remains **7/24 versus 2/24 complete test passes**,
with differences **0, +2, +3** across draws: the prespecified repeatability
screen failed. No threshold, outcome, prompt or closed-study artifact is changed.

The immediate milestone requested by the user is completed here: an exhaustive
code/test ledger, a distinction between observations and hypotheses, and one
[falsifiable next ablation](NEXT-EXPERIMENT.md). The final selector objective is
still unachieved. There are no new model calls, fees, allocations or holdout exposures.

## What the audit establishes

| Observed outcome | Feedback | Spectrum |
| --- | ---: | ---: |
| Selected responses | 24 | 24 |
| Complete public + evaluator test passes | 2 | 7 |
| Valid JSON file mappings | 23 | 23 |
| Syntactically valid Python outputs | 20 | 19 |
| Invalid/incomplete file mapping | 1 | 1 |
| Python load errors | 3 | 4 |
| Public failures involving runtime exceptions | 1 | 1 |
| Other public behavior failures | 14 | 11 |
| Public pass, evaluator failure | 3 | 0 |
| Outputs fixing at least one initial public failure | 9 | 10 |
| Outputs breaking at least one initial public pass | 7 | 7 |
| Total newly broken public cases | 23 | 23 |
| Outputs with identical source AST | 3 | 0 |

The six rows from complete passes through public-pass/evaluator-failure form an
exhaustive outcome partition when excluding the two validity-count rows. Gain,
regression and AST rows overlap those categories. A runtime exception is an
observed symptom, not proof of an infrastructure defect. Invalid mappings have
no fabricated test outcomes; their gain/regression lists remain null.

**Seven outputs contain an unmatched final `}` inside the Python source string.**
All seven raw responses are valid JSON; parsing that JSON yields exactly the
stored code, including the brace. The harness did not append it. The strict
decoder distinguishes a valid file mapping from valid Python syntax. These
seven outputs remain failed repairs, with their 92 original suite executions
across all 46 valid mappings already independently replayed at publication.
The separate two invalid mappings are both on youtube-dl-020: spectrum draw 1
violates the output contract; feedback draw 2 ends at the 4,096-token limit with
an unfinished, mostly whitespace response. No salvage or rescoring is performed.

Formatting is therefore a real failure mode, but cannot explain all failures:
**39/48 outputs parse as Python and only nine pass all frozen tests**. This is
not a counterfactual estimate of what automatic syntax repair would achieve.

## What changed in the successful cases

Draws below are numbered 0, 1 and 2 as in the frozen plan. Full details, original
instructions, numbered source, all 48 diffs and every failing test witness are
in [CASES.md](CASES.md); exact attempt IDs are in [audit.json](audit.json).

| Bug | Feedback successes | Spectrum successes | Observed code/test difference |
| --- | --- | --- | --- |
| youtube-dl-013 | none | 1, 2 | Successful spectrum outputs replace an HTTP-only path check with a generic scheme-prefix check and retain a non-string guard. Feedback draw 0 handles more schemes but raises TypeError on a list path; draw 2 enumerates schemes and misses `abc+v1` and `srt`; draw 1 still misses the public RTMP case. Spectrum draw 0 also misses it. |
| youtube-dl-033 | 0 | 1, 2 | Successful outputs remove the fractional substring before parsing the timezone/date. Feedback draw 1 handles fractional `Z` but not signed offsets; draw 2 loses the timezone adjustment. Spectrum draw 0 matches the fraction but slices at the start of the timezone subgroup, leaving the fraction and raising ValueError. |
| youtube-dl-043 | 1 | 0, 1, 2 | Successful outputs allow repeated path components. Feedback draw 0 fixes the deep path but breaks query/fragment cases; draw 2 contains the unmatched Python brace. |

These account for all **six spectrum-only paired successes and one feedback-only
success** (youtube-dl-033, draw 0). They do not show that the model used a
particular ranked line or that Ochiai caused the gain. Both conditions already
contained complete public expectations and failed observations. The diagnostic
condition also repeated source excerpts and changed prompt length.

Even a complete test pass is not a correctness proof. In both accepted
youtube-dl-013 spectrum outputs the new regex accepts any valid scheme followed
by `:`, although the written requirement specifies `://`. Static inspection
therefore flags a possible acceptance gap for a non-hierarchical path such as
`mailto:x` with no base. **This is an unexecuted, analyst-proposed counterexample,
not a newly measured failure or a revised score.** A future verifier version
must resolve the specification independently; this exposed case cannot become
unseen evaluation data. Fractional timestamps without a timezone remain explicitly
out of scope in the current specification; accepting those is not counted as a defect.

## All five never-repaired bugs

| Bug | Evidence from all six outputs | Interpretation and remaining uncertainty |
| --- | --- | --- |
| youtube-dl-003 | All six still fail the public stray-ampersand example. Feedback outputs retain the same AST in all three draws. Spectrum draw 0 changes the callback wrapper, draw 1 rewrites entity handling and regresses named/unknown entities, draw 2 adds an HTML5 lookup. All retain the broad `&([^;]+;)` matching boundary. | The returned code does not correct the boundary that absorbs a stray ampersand and the following entity together. The top-ranked source line is the unknown-entity return, a downstream symptom. This does not prove that ranking distracted the model. |
| youtube-dl-020 | Neither executable attempt fixing the pattern passes boolean-attribute cases. Feedback draw 0 removes a `%s` placeholder while retaining a two-value interpolation and raises TypeError; spectrum draw 0 has a Python load error. Feedback draw 1 and spectrum draw 2 return no match for the public boolean attribute. The other two outputs are invalid/incomplete. | Pattern construction, output serialization and incomplete attribute handling coexist. Coverage ties all seven failing-executed lines at the same score and does not distinguish positions inside a multiline regex literal. No single bottleneck is established. |
| youtube-dl-031 | All three feedback outputs and spectrum draw 1 retain an unanchored hours fallback with an optional unit: `3 min` returns 10,800 rather than 180 seconds. Spectrum draws 0 and 2 fail to load. Draw 0 adds end anchors, but its code cannot execute as returned; draw 2 retains the overly permissive fallback. | Wrong branch matching persists in executable outputs. The highest-ranked line is the hours return, rather than an explanation of why that branch matched. A potentially useful edit in invalid code is not a successful repair. |
| youtube-dl-042 | Feedback draws 0/1 and spectrum draw 1 fail to load. Feedback draw 2 mismatches semicolon handling and fails both initial public failures. Spectrum draw 0 fixes the single existing-entity case but drops other text; draw 2 still escapes a valid entity and misses the second raw ampersand. | Matching span, terminator handling and preservation constraints remain inconsistent. Fixing one symptom can erase useful text or break previously passing numeric entities. |
| httpie-005 | Four outputs fix the simple escaped colon (feedback 0/2, spectrum 1/2), but all six fail the escaped multi-character `:=` case. The four improved outputs skip or reject the colon but still split on the equals sign inside the escaped separator. Feedback 1 and spectrum 0 do not handle escaping. | Separator priority alone does not implement atomic skipping of an escaped multi-character token. The broad nine-line top tie does not supply that operation. No evidence here distinguishes missing understanding from insufficient use of the prompt. |

The strongest supported diagnosis is **heterogeneous repair failures**: unchanged
or ineffective edits, serialization/load errors, and incomplete implementation
of parsing/preservation requirements. It is not simply lack of a failure
location, insufficient parameter count, or a proven harmful effect of diagnostics.
The five hard bugs are retained in every descriptive count and will not define
an exclusion rule for future sampling.

## Consequence for the selector goal

The next hypothesis is deliberately narrower: **does truthful test-association
information help beyond repeating the same source locations?** The next design
compares full diagnostics with a source-excerpt control and the original feedback
baseline on fresh development bugs, with a separate untouched replication later.
It preserves invalid outputs, regressions and verifier gaps. It does not bundle
a formatting repair into one arm or assume every failure needs more information.
Only a useful, replicated intervention would justify an equal-total-resource
policy comparison and then a prospective selector.

## Reproduction and provenance

From the repository root:

```bash
uv run python experiments/python-repair/checkpoint-environment/results/spectrum-screen-20261030/reproduce.py
uv run python experiments/python-repair/checkpoint-environment/results/spectrum-posthoc-20261030/reproduce.py
```

The first command independently verifies the original frozen report, prompts,
receipts and scores. The second recomputes all facts and diffs from the immutable
archive, checks exact identities for all 48 cells and test cases, literal JSON
decoding, syntax flags and agreement with original scores. It compares the
derived audit.json and CASES.md byte-for-byte. It parses code but never executes
it, imports collector modules, loads credentials or contacts a provider. Use
`--write` only to regenerate derived audit artifacts; it never writes the source bank.

Manual interpretations and the next-experiment proposal are authored analysis,
not outputs of the numerical verifier. This audit is post hoc, development-exposed,
concentrated in two projects, and cannot establish causal mechanisms, scaling
laws, untouched-task performance or selector value. Four untriggered source
candidates remain in provenance and have no invented recovery outcomes.
Source attribution is retained in the excerpts; licenses are preserved under
[development/licenses](../../development/licenses/).

Study cost and cumulative commitment remain **$0.02687800** and **$0.25463059**
respectively, including fourteen historical uncertain reserves once. The current
audit uses local analysis only; local work is not claimed to have zero resource cost.
