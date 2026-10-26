# One-request wire-envelope validation

Prospectively declared 2026-10-26 after the closed SSE compatibility probe. Its
three requests, missing long response and inconclusive gate remain unchanged.
This is a distinct engineering test of the explicit larger client wire cap,
not a continuation that fills the old fixture or an efficacy experiment.

Send exactly one new synthetic request asking for a JSON array enumerating all
integers 0 through 8191. It contains no clamp functions, bug or reference fix.
The intentionally longer-than-budget output is expected to stop at the 4096-token
limit. A complete `length` receipt is valid transport evidence even though the
JSON text may be truncated; it is not a correct solution or a model failure score.

`transport_probe.packet('repair-sse-wire-envelope-v1')` fixes the exact body and
identity. Pin Qwen3-Coder-Next, Parasail/BF16, temperature 0.7, seed base 43134,
32768 input reservation tokens and 4096 output tokens, $0.12/$0.80 per million
price ceilings. Explicitly freeze **8,388,608 wire bytes**; all parsing, identity,
usage, deadline-at-read-boundary and uncertainty rules remain in force.

Separate allocation **$0.01** within **$0.60**; carry **$0.11456635** once including
twelve unresolved requests. Maximum new reservation **$0.00720896**, maximum
planned cumulative commitment **$0.12177531**. Agent-declared under the standing
continuation instruction, not a newly typed user budget. No recycled allocation.

Commit and pass full offline checks plus exact-source CI before freezing and
launching once. The prior report, protocol/config, requests and source commit are
bound in the freeze; a distinct fixed study claim prohibits relaunch. Read-only
endpoint/credit checks precede dispatch. No retry, fallback, key rotation,
replacement, resumption or API generation lookup; retain uncertainty or larger
reported overage. An error ends this one-request test. Never repurpose its missing
outcome as a later request to the same fixture.

The fixed engineering criterion requires **all** of: one complete validated
receipt; wire bytes above 1,048,576; exactly 4096 reported output tokens; and
`finish_reason: length`. A shorter answer or missing receipt is inconclusive for
this criterion. Do not change the threshold after seeing the response.
A pass permits preparation of a separately declared scientific calibration;
it does not pass the old three-fixture gate, estimate reliability, identify the
cause of old resets, establish repair/trace benefit or authorize selector fitting.

After a verified terminal process, audit all selected cells, receipt/ledger,
wire metrics and cumulative costs, export frozen evidence and reproduce the
audit independently. Partial wire text is not archived or scored. Preserve old
uncertainties and protocols unchanged. Freeze review must check the new body
and identity are disjoint from the three closed synthetic requests.
