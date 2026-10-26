# First pilot interruption and proposed manual exception

The first live segment used source commit `eb675a26118813b8aa1f4a7ccdf7ef9344ee7b68`
and prospective freeze `f8087fa062a63897e1359921326cd5667100672230e2bf0f819edbc9f1f9a46d`.
It stopped after 11 admissions: 10 accounted responses ($0.00086600) and one
unresolved $0.00151552 reservation. The conservative committed total is
**$0.00238152** against the authorized **$0.60** cumulative cap.

No response payload was received for the last admission. Its scientific outcome
and actual charge remain unknown. The original adapter preserved the reserve
and stopped without retry, but recorded only the exception class, not the HTTP
status or transport category. The precise transport cause cannot be recovered
from these records. The subsequent code change preserves these safe diagnostics;
it does not alter the original records, treat the charge as zero or resend the
request. Audit verified all ten saved observations and their request/receipt/
artifact relationships. There is no completed calibration or model-efficacy claim.

The 24-trajectory schedule started `task-004-rep-00` and `task-003-rep-01`; one
trajectory finished before the interruption. The original directory is immutable:
`runs/repair-gemma4b-development-v1-20261026`. The failed branch remains censored.
All earlier campaigns remain closed and the historical heartbeat stays paused.

## Reviewable proposal, not launch authorization

The [continuation draft](PILOT-CONTINUATION-DRAFT.json) enumerates the **22 original
trajectories never started**, in their original order, and hashes every parent
record. Neither of the two started trajectories would be resumed, even for its
unsubmitted calls. This is a conservative reduction of the original design;
the lost states/draws must remain missing in the final development report.

Task hashes, model/provider, temperature, prompt projection, paired seeds,
verifier, prefix/branch logic and per-checkpoint allowance remain fixed. The
maximum remaining count is 330 calls. The new segment's accounting allowance
would be `$0.60 - $0.00238152 = $0.59761848`, not another $0.60. Maximum planned
new reservations are $0.50012160, giving **$0.50250312** including retained prior
charges/reserves. Actual charges and pending reservations remain separate.

The successor checks the complete parent hash map and its audited committed
cost, rejects any started trajectory or overlapping admission, subtracts the
parent commitment exactly once, and claims a unique successor to this parent
freeze. Changed/missing parent files, altered settings or another successor
fail closed. A future failure stops again; there is no automatic retry/resume.
Original source freezes and this amendment must remain visible alongside any
combined analysis. No inspected development task becomes a held-out task.

The original protocol forbids automatic resumption and requires a manual review
and explicit exception. The draft therefore has `live_calls_enabled: false` and
no authorization reference. **Do not launch it without the user's authorization
for this exception; no additional money is requested.** After authorization,
record it, commit the amendment and freeze the successor before any calls.
