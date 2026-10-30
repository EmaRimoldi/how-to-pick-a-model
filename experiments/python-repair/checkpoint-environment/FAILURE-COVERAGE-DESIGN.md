# Candidate revision: cover the remaining public failures

Status: offline engineering preparation after the failed contrastive development
screen. The subsequent prospective decisions are specified in
[FAILURE-COVERAGE-PROTOCOL.md](FAILURE-COVERAGE-PROTOCOL.md). **Not a frozen model protocol, allocation, selector or positive result.**
The final user objective and all historical studies remain unchanged.

The [terminal audit](results/contrastive-calibration-20261026/POSTHOC.md) found
46 responses fixing some public failure but only 24 complete repairs. In one
case, five trace-bearing responses fixed the selected failure while leaving a
second known failure. This motivates testing coverage, without proving that the
first-failure focus caused the incomplete repairs. The eight old checkpoints
are poor evidence for this revision: only two have multiple public failures.

The [broader development pool](development-broader/README.md) adds six adapted
bugs across four previously exposed projects. Every initial buggy artifact has
two to four public test failures, often manifestations of one underlying defect.
They are not independent bugs or necessarily multi-defect programs. Engineering
qualification is complete, but a coding model may solve them immediately or fail
uniformly; difficulty and useful action headroom remain empirical questions.
The prepared traces use original buggy checkpoints. The proposed model study
should first collect one repair attempt per bug, then compare recovery actions
only at resulting public failures. This makes the recovery artifacts natural
model outputs rather than manually constructed partial patches.

## The concrete comparison

Keep code, instructions, all public inputs/expected values, complete public
feedback, model/provider/precision and generation limits identical. Compare:

1. Repair directly from code and public feedback.
2. Acquire a bounded trace of the first public failure, then repair.
3. Acquire bounded traces of all currently failing public cases, then repair.

The third option acquires runtime states, not previously hidden test answers.
Public order determines acquisition; no private cases, fixed-source values,
future outcomes or task-specific hand-written hints select a trace. A six-case
suite bound is enforced before execution. Every selected case costs an ordinary
invocation and a trace. An unavailable trace stays recorded; available records
are retained with explicit incomplete coverage, without retries or substitutions.

The implementation binds diagnostics to the exact current files and public
feedback. An artifact changed by a partial repair needs fresh feedback and new
diagnostics; stale evidence is rejected. The current preparation uses original
buggy artifacts only and does not yet test this later-checkpoint hypothesis.

## Required scientific and resource decisions

A potential two-stage calibration starts with six initial repair attempts on
the native buggy programs. Retain every initial result, including public passes
that fail private evaluation. Only public failures trigger the second stage:
three conditions × three matched draws per failed checkpoint, at most 54 more
requests, or **60 total**. Public-pass artifacts are not silently modified to
create harder cases. If too few failures remain, report insufficient recovery
coverage rather than expanding the cohort after observing model outcomes.

Freeze the task/initial-attempt protocol and conditional rule before the first
request; freeze exact derived recovery prompts after the initial stage ends and
before any recovery call. Do not reuse a historical source prefix or control.
Before collection, freeze the primary coverage comparison,
the baseline comparison and repeatability/missingness rules. A favorable direct-
repair comparison alone cannot establish the added value of broader coverage
over the existing first-trace strategy. Keep all bugs, false public acceptances,
regressions, unusable outputs and missing outcomes. Do not tune or choose the
criterion after looking at responses. No training follows from engineering QA.

The largest measured message is 19,484 UTF-8 bytes. With a conservative 4,096
framing allowance, the older 18,432 input reservation is insufficient. A 25,600
input reservation plus 4,096 output tokens at the earlier price ceilings
$0.12/$0.80 per million would reserve $0.00634880 per call, or $0.38092800 for
60 calls. With the current $0.20640271 carry, that is $0.58733071 under the $0.60
campaign ceiling. Derived model artifacts may be longer than native sources;
the future protocol must retain oversize/admission failures and must not assume
that all possible recovery messages fit this reservation. **This is a feasibility calculation, not a new allocation or
verification of current provider pricing.** Recheck actual endpoint settings,
pricing and all budgets at the later freeze; never raise the campaign ceiling
or discard the thirteen historical uncertain reserves implicitly.

Equal per-call limits would establish an intervention calibration, not an
equal-total-resource selector result. A later policy comparison must enforce
shared API and local-time limits, include source-prefix work, diagnostic
selection/execution/projection, failed attempts, uncertain charges and final
verification, and retain direct retry/restart, always-diagnose and the strongest
fixed strategy. Any selector must choose before obtaining its diagnostic for
free and be evaluated on untouched grouped bugs. All inspected development
sources and variants remain excluded from that evaluation.

## Evidence delivered now

- Original definitions, provenance, licenses, all considered candidates and
  the initial adapter failure are preserved in the broader pool.
- All six published buggy/fixed pairs qualify twice on disjoint public/evaluator
  inputs, using the unchanged verifier.
- Both acquisition variants match ordinary execution and the same core prompt;
  the shared first trace and retained-value encoding roundtrip agree.
- Tests reject stale feedback/private fields, retain unavailable selected cases,
  check execution accounting and perform no acquisition when public tests pass.

No paid request is enabled. The next step is a separately reviewed, budgeted and
frozen model calibration, not a learned selector or a held-out performance claim.
