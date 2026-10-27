# Transport review after the interrupted Qwen information study

The closed [information bank](results/information-qwen-stopped-20261026/README.md)
retains 18 responses, one uncertain request and 45 never-admitted requests.
Its primary result remains inconclusive. This review changes neither its protocol
nor its outcomes and authorizes no replay, resumption, successor or new API call.

## Observed facts and unestablished causes

The saved transport kind is `TimeoutError`, with no recorded HTTP status or
structured provider error. The client used a 180-second blocking socket-operation
timeout and non-streaming requests. This is not a measured total wall-clock
deadline. The successful receipts span 3.443–14.111 seconds, with median 6.416.
Those timings exclude the failed request and cannot explain it. The old log
cannot distinguish connection/upload/header waiting from reading the response.
It establishes neither a rate limit nor that a longer timeout would fix the issue.

The provider implementation now records a bounded phase label and elapsed time
on future transport exceptions: awaiting response headers, reading the body, or
decoding JSON. The first phase still combines several network/server stages.
Timeouts and incomplete response bodies keep their full reservation and stop the
collector. Offline injected failures verify one dispatch, no retry, no invented
settlement, safe diagnostics and closure of an acquired response handle. Request
bodies, sampling settings, pacing, fallback policy and timeout are unchanged.
These checks improve diagnosis; they do not demonstrate service reliability.

## Consequences for a separate future protocol

[OpenRouter's streaming documentation](https://openrouter.ai/docs/api_reference/streaming),
checked 2026-10-26, describes keep-alive comments and a final usage event. It also
warns that disconnecting a non-streaming request does not cancel processing or
the charge. Streaming errors can arrive after HTTP 200. Therefore an apparent
connection success or partial generated code is insufficient for settlement.
This supports retaining the uncertain charge; it does not identify our timeout's
cause or prove streaming would have prevented it. No streaming change has been
made to the completed experiment.

A new independent study should prospectively separate a missing request from
the disposition of later, independent, never-admitted cells. A bounded policy
could retain the entire uncertain reserve, record that cell as missing without
replacement, and allow the next scheduled cell after a fixed cooldown, subject
to an exact error-count stop and cumulative commitment cap. Authentication,
pricing/identity mismatches, unexpected receipts and accounting failures should
remain terminal. Such a policy needs its own audited collector and fault tests;
the current collector still stops on its first error. Do not retrofit this rule
to recover the closed bank's missing cells or call it the same preregistered study.

Before adopting streaming, separately validate SSE framing, keep-alives, partial
JSON, repeated terminal markers, final usage, provider/model identity and missing
terminal receipts with injected failures. A transport change is part of the new
source freeze, not a reason to relax scientific or financial missingness rules.

The [three additional development adapters](development-extension/README.md)
provide independent task inputs for a subsequent calibration design, not a fresh
evaluation sample. First check whether they provide nontrivial solver headroom;
three small bugs alone cannot validate a general acquisition policy. Keep the
current cumulative commitment at **$0.08592275**, including all nine unknown
requests. Any future collection needs its own declared allocation within the
standing ceiling, reviewed protocol and clean source freeze. Unspent allocations
from closed studies do not become an automatic continuation budget.


## Subsequent independent extension: response-body resets

The [separate extension protocol](EXTENSION-INFORMATION-PROTOCOL.md) implemented
and froze the proposed single-uncertainty rule. Its [terminal bank](results/information-extension-stopped-20261026/README.md)
contains 11 admissions, nine received responses, two uncertainties and thirteen
never-admitted cells. After the first retained unknown the collector waited
120 seconds and admitted only new independent cells. The second error stopped
it, as specified. There was no retry, replacement, resumption or key rotation.

Both exceptions were `ConnectionResetError` during `reading_response`, at
14.968684 and 12.188266 seconds of recorded exchange time, without an HTTP status.
They were not recorded rate-limit responses or 180-second timeouts. This narrows
the failure phase but does not distinguish a local-network, intermediary or
service cause. The old timeout remains a different observation with no phase
record; do not retroactively infer its cause from these resets.

Both reserves ($0.01441792) remain, bringing cumulative commitment to
$0.10576463 / $0.60 including eleven unresolved calls. All scientific banks are
closed and incomplete outcomes remain missing. Before another collection,
validate a transport change independently with failure injection and a separately
reviewed prospective allocation. Streaming is still a candidate, not an established
fix. Do not modify or reuse the closed schedules to test it.


## Prospective SSE compatibility implementation

The opt-in `src/vao/repair/streaming.py` leaves historical collectors unchanged.
Offline fixtures cover byte-split UTF-8, SSE line endings and multiline data,
terminal accounting, HTTP/body failures, identity changes, malformed framing,
cost overages, missing terminal receipts and secret echoes split across chunks.
An incomplete stream retains its reservation; complete generated-but-invalid
content remains a billed observation. Raw partial text is not persisted.

The [separate compatibility protocol](SSE-COMPATIBILITY-PROTOCOL.md) and one-use
collector prepare three synthetic payloads, without scoring repair or inspecting
new benchmark tasks. This makes the engineering check bounded and reviewable;
it does not establish that streaming resolves the observed resets. Runtime proxy
inspection found no configured urllib proxy schemes in this process, which
excludes neither system/network intermediaries nor changes at collection time.


The [terminal SSE probe](results/sse-compatibility-20261026/README.md) returned two
complete receipts; its third request reached the client's 1 MiB wire limit at
1,048,653 bytes after 50.538 seconds. This is an identified client envelope-sizing
defect, not a recorded connection reset. The limit was checked before a terminal
usage frame, so the charge remains unknown/reserved and the fixed gate
inconclusive. No partial text is scored, and no closed request is repeated.

A post-terminal synthetic regression with 4096 content frames reproduces the
1 MiB failure and completes with an explicitly configured 8 MiB cap. The adapter
now accepts a declared cap between 1 and 16 MiB; v1 keeps its historical 1 MiB
default. Future freezes must explicitly select the larger tested cap and retain
all other accounting guards. This is offline sizing evidence, not proof of
live long-response completion or a reason to reinterpret the prior resets.
Cumulative commitment is $0.11456635, including twelve unresolved requests.


The separately frozen [wire-envelope validation](results/sse-wire-envelope-20261026/README.md)
then received a complete final usage record after 1,112,924 wire bytes and all
4096 output tokens, with `length` finish and the explicitly configured 8 MiB
cap. All four declared engineering conditions hold. This is one observed
exchange, not a reliability estimate or a causal streaming comparison. The old
three-fixture bank remains inconclusive and its unknown is unchanged. New charge
$0.00328916 brings cumulative commitment to $0.11785551, with twelve old uncertain
requests and no new uncertainty. Further work returns to separately frozen
scientific calibration; no source or budget from a closed bank is resumed.


## Separate scientific streaming bank: timeout after partial output

The [64-request matched streaming calibration](results/information-stream-stopped-20261026/README.md)
received one complete response before its second request stopped under the frozen
first-error rule. It recorded `TimeoutError` during `reading_stream` at 182.59655
seconds. First bytes arrived at 1.168395 seconds; 143 chunks / 39,830 bytes /
482 content characters were seen without finish, usage or DONE. No parser error
or HTTP status was recorded, and the explicit 8 MiB cap was not approached.
This observation does not identify the root cause or prove that increasing the
timeout would work. The previous sizing correction remains valid but insufficient
to establish end-to-end reliability.

The unknown is reserved, not retried or scored. With 62 never-admitted cells,
63/64 selected outcomes are missing and the scientific gate remains inconclusive.
Known charge $0.00078680 plus reserve $0.00720896 brings cumulative commitment to
$0.12585127, including thirteen uncertain requests. All collectors are closed.
A later acquisition design needs to account for recurrent infrastructure loss
prospectively; neither the old missing cells nor the old complete-bank gate may
be reinterpreted after observing this result.


## Later independent-cell bank completed

The [independent-cell calibration](results/information-independent-20261026/README.md)
completed all 64 scheduled requests, with complete receipts and no new unknowns.
Its prospective retention/cooldown rule was not exercised by a live error.
This is evidence that this schedule completed under the pinned streaming setup;
it does not identify historical failure causes or establish a comparative
reliability effect. The scientific benefit screen failed separately. All prior
uncertain reservations remain included in $0.16495655 cumulative commitment.
