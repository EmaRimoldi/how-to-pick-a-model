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
