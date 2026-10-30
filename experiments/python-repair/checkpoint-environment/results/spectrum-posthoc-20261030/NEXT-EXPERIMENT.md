# Proposed ablation: information versus repeated source excerpts

Status: **offline design proposal, not a preregistration, funded collection or
launch authorization**. No new model call has been made. This follows the
[aggregate-known post hoc audit](README.md) and does not amend the closed study.

## Question and falsifiable contrast

Does truthful public-test association at a failed checkpoint improve complete
repairs beyond presenting the same executed source excerpts without those
associations? The current 7-versus-2 result cannot isolate these components.
The code audit also shows that a ranked symptom is not an implementation of the
required parsing rule, and that invalid output is a competing failure mode.

Use one three-arm experiment with a single diagnostic-information ablation:

| Arm | Content supplied before one repair |
| --- | --- |
| F: feedback | Identical task, current files, all public inputs/expected outputs and current public feedback. |
| N: neutral excerpts | F plus every covered source location and its code text, in canonical filename/line order. Test-outcome associations, passing/failing counts and scores are absent and marked `not supplied`. |
| S: scored excerpts | The same locations and code in the same canonical order, with their true passing/failing execution counts and exact squared Ochiai values. All ties and zero scores remain visible. |

**Primary contrast: S minus N** in complete public-plus-evaluator repair rate,
paired by checkpoint and averaged within bug before aggregating bugs. Keep F
as a safety/reference baseline: S beating N alone, while losing to F, is not
useful acquisition. S minus F and N minus F are declared secondary contrasts,
never replacements for an unfavorable primary result.

N intentionally shares the union of covered locations with S. This isolates
outcome association conditional on the same coverage/excerpt selection, not the
value of coverage collection itself. Do not retain suspiciousness ordering in N,
substitute false scores, or call a shuffled misleading diagnostic neutral.
Canonical source order in S differs from the previous rank-sorted representation:
this is a new ablation, not an exact replication of the old prompt package.

This controls location selection, code repetition and ordering, **not exact
token count or cognitive content**. Measure prompt tokens and all costs. If exact
length matching is desired, its tokenizer and neutral padding rule must be frozen
before collection, and the padding itself remains a limitation. Equal generation
caps are not equal total resources.

## Prepare before any collection

1. Review specification/verifier consistency using only already exposed development
   material. Keep original results intact; version future adapters and record
   specification resolutions. The static scheme-prefix concern on youtube-dl-013
   is a development issue, never fresh validation evidence.
2. Freeze a new development manifest before seeing any model response. Group by
   upstream bug/project, keep duplicate adapters together, and retain all initially
   selected candidates. Public-only failed-checkpoint eligibility is declared in
   advance. Log and charge initial attempts, including untriggered public passes;
   audit acceptance gaps separately rather than assuming they are solved.
3. Qualify the builder offline: F/N/S share identical code, public feedback, cases
   and output contract; N/S share location sets and order; S labels derive only
   from public executions; private evaluators/reference fixes cannot enter prompts.
   Check ordinary/covered execution agreement and document flat spectra. An
   uninformative ranking is a retained case, not grounds for exclusion.
4. Freeze one model/provider/precision, sampling settings, balanced arm order,
   independent repeated draws, exact request bodies, missing-data rules, analysis
   and a declared spending ceiling before launch. Keep output encoding unchanged
   across arms; invalid JSON, syntax errors, truncation, regressions and exceptions
   count as outcomes. No automatic code salvage, retry or new formatting arm.
5. Determine sample size from a declared practically meaningful effect and a
   prospective precision/power calculation at the bug level. Eight exposed bugs
   and three draws are not a population-level sample-size justification. Choose
   the smallest useful effect before the new outcomes; publish the calculation
   and exact stopping rule. This proposal deliberately supplies no invented
   precision estimate or post hoc threshold.

## Decision rule to freeze, then test

Use a fixed sample and all selected cells, no outcome-dependent extension.
Before collection, fix a minimum useful improvement and the uncertainty procedure
at the bug/project level. Advance only if S exceeds N by that prespecified
criterion, also offers a useful improvement over F, and the result repeats on
an untouched grouped replication. An incomplete bank remains incomplete;
report missingness and finite completion bounds without imputing success or
dropping interrupted cells. Freeze exact numerical criteria with the sample-size
calculation; this design is not runnable until those choices and resources exist.

Preserve an unfavorable result. If S and N are similar, the evidence does not
support score information as the useful component. If both improve on F, excerpts
become a candidate explanation, not a causal conclusion borrowed from the old bank.
If neither helps, do not fit a selector whose only purpose is to choose them.
If syntax failures dominate a new bank, any output-contract experiment is a
separate study applied symmetrically, not a rescue of selected failed responses.

## Route back to the final goal

Only after independent evidence of useful acquisition, compare fixed policies
under enforced equal **total** resources: retry directly, always acquire, and
stop. Charge acquisition, candidate generation, verification, selection, initial
attempts and all failures. Keep API money, local compute and latency explicit;
do not silently equate them or omit shared-prefix cost. A retrospective oracle
can measure headroom, but is not a deployable selector.

Then fit a small selector on development bugs using information available
**before** acquisition. Split entire bugs/projects before fitting or choosing
thresholds. Freeze it and evaluate once on fresh groups against the best fixed
policy selected on development, with the same enforced resources. Success is
more solved tasks at that budget, with uncertainty and failure accounting—not
better classification of a label constructed after observing both alternatives.

The immediate engineering deliverable after accepting this proposal would be
the public-only N/S builder, offline boundary tests, fresh development manifest
and numerical sample/resource freeze. No selector training or collection is
enabled by this document.
