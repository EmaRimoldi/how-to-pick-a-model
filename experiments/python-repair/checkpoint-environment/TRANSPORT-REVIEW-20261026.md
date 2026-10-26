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
