# Prospective public-contrast development calibration

Study: `repair-qwen-contrastive-trace-development-v1`. This is a new, bounded
study after the complete independent trace bank failed its benefit screen.
It tests the [revised intervention](CONTRASTIVE-DIAGNOSTIC-DESIGN.md), without
changing any historical analysis or training a selector. The human objective
in GOAL-AMENDMENT-20261026.md remains incomplete.

## Question and exposure

Does a bounded pair of failing and already-passing public executions improve
complete repair over the same code and feedback alone? All twelve original
27B-generated checkpoints remain in provenance. Qualification uses public
feedback only: eight public failures (seven youtube-dl, one httpie) trigger
repair; four public passes do not, including known evaluator failures.
All these sources and earlier outcomes have been inspected. This is explicitly
development, not held-out validation, a scaling experiment or a new benchmark.

Three concurrent arms are fixed:

- `focused`: current code, instructions, existing public tests and observations,
  with the first failure highlighted.
- `single_trace`: the same core prompt, plus a bounded failure trace in the
  v2 lossless representation.
- `paired_trace`: the same core prompt and first trace, plus the trace of one
  already-passing public case selected by the fixed public-input heuristic.

Only `runtime_diagnostic` differs within a triplet. No evaluator expectations,
reference values or new test oracles enter prompts or selection. Public traces
must agree with ordinary execution and stored public feedback. Failure to
acquire a diagnostic is retained, never excluded. All eight currently eligible
sources passed offline acquisition qualification; that is not efficacy evidence.

Use three matched draws per arm per eligible bug: **72 fresh requests**, 24 per
arm. Three draws preserve the 4096-token output allowance while covering all
three concurrent conditions under the existing cumulative cap. This new gate
does not revise any earlier four-draw gate. Shuffle the 24 task/draw triplets
with seed 43137; shuffle all six arm permutations with seed 43138 and cycle them,
so each permutation occurs four times. The three members share a generation
seed. Fresh attempt IDs and actual provider bodies must be disjoint from the
**620 unique planned bodies in fifteen historical archives**, including unsent
bodies. No pooling, filling or historical controls.

## Solver, limits and operational stopping

Pin Qwen3-Coder-Next, Parasail/BF16, temperature 0.7, JSON-current contract,
maximum 4096 output tokens, 18432-token input reservation and price ceilings
0.12/0.80 USD per million input/output tokens. Input acceptance uses the existing
conservative UTF-8 message-byte plus 4096 framing allowance; actual usage is
checked against the reservation. The input reservation is a financial bound,
not a claim about the provider tokenizer. No fallback or key rotation.

Streaming uses the existing 8 MiB envelope, 180-second socket idle timeout and
300-second wall check at read boundaries, not a hard end-to-end deadline.
A receipt requires final usage and DONE; billed malformed/truncated outputs
remain unsuccessful outcomes. At least 60 seconds between new requests.

The independent-cell network rule is unchanged from the last complete bank:
retain full reserves for allowlisted no-receipt network failures; after a
recorded 120-second cooldown, admit only the next never-admitted scheduled cell.
At most seven such errors may unlock another request; the eighth total or third
consecutive stops. The allowlist is TimeoutError, URLError, RemoteDisconnected,
IncompleteRead and ConnectionResetError during awaiting_response_headers or
reading_stream, without HTTP status, receipt, usage/cost, DONE or parser error.
Every other error is terminal. No retry, resumption, successor or substitution.
A crash during cooldown leaves the durable reserve and no further admission.

Never inspect arm outcomes, means, bounds or gates while collection is active.
Use `scripts/check_repair_contract_progress.py` for request identity, progress
and accounting only. Outcome information never controls dispatch or stopping.
Exhausting the schedule with unknown cells is terminal incomplete, not a
successful complete seal.

## Separate allocation and resources

[CONTRASTIVE-STUDY-AUTHORIZED.json](CONTRASTIVE-STUDY-AUTHORIZED.json) declares
**0.40 USD** under standing user instructions to continue, within the retained
**0.60 USD cumulative cap**. This is an agent-declared suballocation, not a newly
typed user amount or unlimited spending. Carry **0.16495655 USD exactly once**,
including thirteen historical unresolved reserves. Each new maximum reservation
is **0.00548864 USD**; 72 sum to **0.39518208 USD**. Maximum planned cumulative
commitment is **0.56013863 USD**; carry plus full allocation is **0.56495655 USD**.
Provider/key capacity is checked read-only before admission; no funds are added.

Count all billed failures and unknowns, using the larger of reserve and any
trustworthy observed charge for unresolved requests. Keep paid but unevaluated
outcomes. Report actual API spending separately from counterfactual deployment
resources: source-prefix generation, source public verification, diagnostic
selection/execution and response verification. Single acquisition uses two
sandbox executions; paired acquisition uses four. Cached diagnostics are charged
per planned deployment. Selection/preparation time is included in acquisition
wall time. Local seconds are not converted to dollars. Evaluator-only research
verification is separate. Prompt projection and full deployment overhead will
need additional accounting in the subsequent policy runner.

This one-generation calibration equalizes per-call limits, **not total realized
resources**. It cannot show that a diagnostic policy beats a fixed strategy at
equal total budget, even if its repair count is higher.

## Analysis fixed before collection

Full success requires both public and evaluator suites. Retain every planned
cell, unusable output, public false acceptance, net public-score regression,
missing outcome, untriggered source and charge. Primary: `paired_trace_minus_focused`.
Fixed secondary comparisons: `paired_trace_minus_single_trace` and
`single_trace_minus_focused`. No favorable secondary replaces the primary.

For a complete, uncapped bank, compute each bug's difference in success fraction
across its three matched draws, then the mean across eight bugs. Provide a
**descriptive** 10000-resample bug-cluster bootstrap, seed 43138, percentile
indices 249 and 9749. Replicates are not independent bugs. The small, exposed,
selected bank and prior design iterations preclude confirmatory/generalization
claims. There are no p-values or causal attribution to preservation behavior.

For any incomplete bank, keep all mean/bootstrap fields null, including arms
that happen to be complete. For every contrast with n=24 planned cells per arm,
observed successes sT/sC and missing mT/mC, report selected-cell bounds
[(sT-sC-mC)/n, (sT+mT-sC)/n]. These are finite completion bounds, not confidence
intervals and not an assumption that missingness is random.

The new primary development screen requires all three:

1. At least three bugs with at least two paired-trace full successes each.
2. At least four net additional paired-trace successes versus focused feedback.
3. Strictly positive net paired advantage separately in each draw index 0, 1, 2.

These thresholds must hold under **every binary completion** of missing primary
cells: missing paired outcomes fail and missing focused outcomes succeed in the
least-favorable assignment. The opposite assignment gives the upper screen.
The thresholds are monotone in these assignments. A lower-screen pass permits
only separately reviewed calibration on independent sources, never automatic
selector fitting. If the upper screen also fails, report
`no_completion_meets_development_screen`; otherwise report
`inconclusive_selected_cell_bounds`. A cap overrun is inconclusive regardless
of the screen. Keep original unknowns, never overwrite them with completions.

## Freeze, verification and next decision

Implementation: `vao.repair.contrastive_study`, `contrastive_diagnostics`,
`independent_streaming`, `contract_progress` and `vao.analysis.repair_contrastive`.
Before launch require reviewed clean source, full offline checks, green CI on
that exact commit, fresh source-bound packet, verified origins/prompts/accounting,
exact freeze and single-use admission claim. All old collectors remain closed.

After a terminal record, audit all ordered admissions, receipts, stream metrics,
retention cooldowns, exact prompts and costs. Export inert frozen sources and
independently reexecute saved public/evaluator evaluations and both diagnostics;
reproduce analysis and Markdown exactly. Preserve null results and inspect any
published figure against the report. Raw SSE bytes are not archived, so saved
metrics do not provide byte-level wire replay.

If no useful intervention is demonstrated, do not train a selector to choose it.
Inspect the failed prediction and reconsider acquisition. If it passes, repeat
on separate development sources before a resource-enforced comparison with
strong fixed policies and a selector evaluated on untouched grouped bugs.
This test cannot complete the final research objective by itself.
