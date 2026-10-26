# Independent development-extension information calibration

Status: prospectively declared on 2026-10-26 under the user's instruction to
continue the active diagnostic-acquisition goal. No outcomes from this study
were available when choosing tasks, intervention, analysis or operational rules.
This is a separate 24-request study on three additional task inputs, not a
continuation, replacement or retry of any cell in a closed collection.

## Question, checkpoints and scope

Does a bounded public execution trace improve complete repair over the identical
public feedback without that trace? Use all three prequalified adapters in
[development-extension](development-extension/README.md): Luigi/3, The Fuck/10
and The Fuck/20. Preserve their exact published instructions, source artifacts,
public cases, evaluator cases and explicit adaptation limits. They were selected
on technical criteria before model outputs and are already development-exposed.
The two projects and three bug inputs differ from the closed Qwen information
bank. Do not pool the studies or describe these cases as an untouched evaluation.

These checkpoints are original upstream buggy versions after failed public tests,
not previous LLM-generated patches. Their generated-prefix API charge is zero;
initial verification still costs local execution time. This makes the present
scope ordinary function repair, not proof of recovery from model-written mistakes.
A new general acquisition policy still requires broader development, a costed
policy experiment and an untouched evaluation. The Qwen solver compatibility
screen motivates model choice but cannot establish its difficulty on these cases.

## Fixed matched intervention

Use four draws per bug and per arm: **3 × 4 × 2 = 24 requests**.

- `focused`: code, task instructions, public cases, complete existing public
  feedback and the highlighted first failing public case.
- `focused_trace`: exactly the same payload plus the bounded execution trace
  of that case. No reference patch, private evaluator case, inferred expected
  answer or historical solver response enters the request.

Unavailable or truncated traces remain in the data. Reproduce every public
observation and diagnostic before launch. The prepared traces are available on
all three cases (11, 15 and 10 recorded events), which establishes an executable
intervention, not useful information or an efficacy result.

Pin Qwen3-Coder-Next on Parasail/BF16, temperature 0.7, JSON-object output and
4,096 output tokens. Keep the 32,768 input-token reservation bound and the
4,096-byte framing margin. Seed 43131 shuffles twelve bug/draw blocks; alternating
arm order assigns six blocks to each order. Arms share the provider seed within
a block, without assuming deterministic generation. Keep at least 60 seconds
between admissions. Provider fallback, key rotation and duplicate requests are
forbidden. Exact bodies and identities must differ from the old bank's entire
planned schedule, including its missing and never-sent cells.

## Prespecified handling of operational uncertainty

Use the separate independent-cell adapter, only for this study. A request with
no receipt and a declared transport exception (`TimeoutError`, `URLError`,
`RemoteDisconnected`, `IncompleteRead` or `ConnectionResetError`) while waiting
for response headers or reading the body may be marked missing once. Preserve
its full reserve and identity durably, wait 120 seconds, and proceed to the next
scheduled distinct cell. Never repeat or replace the missing cell, fetch its
unknown generation or change the order based on treatment outcomes.

At most **one** such disposition is allowed. A second error stops the study and
keeps both uncertainties. Any HTTP error, decoding/accounting failure, unexpected
receipt, model/provider mismatch, excessive charge or verification failure is
terminal. No fallback, process resumption or successor is enabled. A crash before
or during the cooldown remains terminal under the single-use launch claim.

Finishing the schedule with a missing cell is not a complete bank: record a
terminal incomplete state, with no imputation or completed-bank gate. This new
prospective rule is not applied retroactively to any closed study. It improves
data retention from independent cells, not provider reliability itself.

## Primary analysis and decision

The only contrast is focused_trace minus focused in full public-plus-evaluator
success on all twelve planned cells per arm. Preserve malformed responses as
observed failures, missing responses as unknown, and every selected bug. Report
regressions, public false acceptance, actual API charges, retained uncertainty,
initial verification, diagnostic acquisition and response verification separately.

On a complete bank, report the paired difference over the three bug clusters
and the existing 10,000-resample descriptive bug bootstrap (seed 43123). With
three purposively selected bugs this interval is unstable and cannot establish
population generalization. Four draws are repeated observations, not independent
bugs. An incomplete bank keeps finite selected-cell bounds, null mean/bootstrap
and an inconclusive screen; do not substitute completed pairs.

Retain the stringent development screen: complete bank, all three bugs with at
least two full trace-arm successes, at least four net additional trace successes
(33.33 percentage points here), and a positive net difference in each draw half
{0,1} and {2,3}. A pass motivates only a separately designed broader and costed
calibration, never selector training. A failed or incomplete screen is retained.
A ceiling on both arms means these cases cannot demonstrate acquisition headroom;
a floor motivates revisiting solver/task or information compatibility. Neither
justifies lowering the gate after seeing results. No interim treatment reads.

A one-generation contrast is not equal realized spending or equal total resource
use: trace input tokens and local acquisition are additional costs. The final goal
still requires beating the best fixed policy under a common total resource cap,
including diagnostic, selection, prefix, failed-call and uncertainty costs.

## Allocation, launch and delivery

The agent declares **$0.18** within the standing **$0.60** cumulative authorization,
under the user's instructions to continue. This is a bounded new study allocation,
not a newly user-typed amount or reuse of the interrupted bank's unspent cap.
Carry **$0.08592275** once, including all nine historical unresolved requests.
A per-call reserve of $0.00720896 makes the maximum planned reservation $0.17301504
and maximum design commitment $0.25893779. Carry plus the full new cap is
$0.26592275. See [authorization](EXTENSION-INFORMATION-AUTHORIZED.json).

Before calls: reviewed exact packet and public-only projections; unchanged
qualified source; passing full workflow and CI on a clean committed freeze;
read-only endpoint/price/credit checks; single-use study claim. No outcome may
alter the design while collection is active. Source changes wait until it ends.

After either complete or incomplete termination, audit all requests, receipts,
missing dispositions and reserves; export inert frozen sources and independently
replay saved verifications and public diagnostics using the existing information
reporter and evidence replayer. Preserve all 24 cells. Update PR20 with the full
result and limitations. A favorable subset or an operational workaround cannot
replace the primary comparison or complete the selector objective.
