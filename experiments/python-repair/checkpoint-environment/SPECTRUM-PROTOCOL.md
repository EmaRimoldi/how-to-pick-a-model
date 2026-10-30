# Public coverage after a failed repair: development screen

Frozen before any new model response. This separate study tests a new diagnostic
representation on historical generated failures. It does not resume the stopped
original-bug region-trace study or fill any of its missing cells.

## Population and intervention

Retain all twelve Gemma 3 27B `json_current` candidates in provenance. Exactly the
eight with a recorded public failure receive repairs: youtube-dl-003, -013, -020,
-031, -033, -042, -043 and httpie-005. Eligibility uses public results only. The
other four have no public trigger; a public pass is not a full-repair claim.
These are already exposed development cases, seven from one project. No unseen
task is read or selected. No historical arm is used as a control.

For each eligible checkpoint compare `feedback` with `spectrum`: the identical
current files, instruction, public inputs/expectations and complete feedback,
plus the saved public-coverage ranking only in the spectrum arm. Render every
covered source line, including zero scores and entire exact ties. Include its
line text, passing/failing execution counts and exact squared Ochiai score.
No ranking cutoff, oracle location, fixed source, private test, generated expected
value, trace resampling or outcome-dependent reformatting is allowed. The system
prompt explains that association is not fault probability and missing behavior
need not appear in the ranking. An unavailable whole spectrum stays unavailable;
the checkpoint is not dropped. This estimates the effect of this whole diagnostic
package, not the isolated merit of Ochiai or a length-matched placebo effect.

Acquisitions come unchanged from `results/generated-spectra-20261029/evidence.zip`
(SHA-256 `91ce9853e359486f7ba40b01e248fb3491d24337fd4c4ceba938e5927744e400`).
They required twelve local executions per checkpoint (ordinary and covered runs
of six public cases). Charge that acquisition to each deployed spectrum action
even though the research cache is shared across draws. Preserve measured time,
prompt tokens, inference charges, generation/verification time and uncertainty
separately. Private evaluation is research-only and is not agent feedback.

## Fixed generation design and accounting

Three draws per arm and checkpoint: 48 new requests. Shuffle the 24 checkpoint/
draw blocks with Random(43141); alternate arm order within blocks. Arms share a
seed per block; different draws use distinct seed inputs. Provider seed support
does not guarantee determinism or independent sampling.

Use Qwen3-Coder-Next, Parasail/BF16, temperature 0.7, 4,096 output tokens,
32,768 conservative input-token reservation, JSON file contract and streaming
with an 8 MiB wire cap. At most one admission per 60 seconds; no fallback, key
rotation, retry, resumption or successor to this collection. Stop at the first
transport/accounting error. Do not analyze arm outcomes before a terminal file.
Malformed model outputs are observed failures; uncertain or never-admitted
requests are missing. Failed local verification is retained, never discarded.

The user's “Ottimo, prosegui” follows a successful separately recorded minimal
availability check, and authorizes proceeding with research. Declare a bounded
new allocation of **$0.36 inside the unchanged $0.60 cumulative cap**. Carry
$0.22775259 once, including fourteen historical uncertain reserves and the
$0.00000924 diagnostic. The per-call reservation is $0.00720896; 48 calls reserve
$0.34603008. Maximum design commitment is $0.57378267; carry plus the full new
allocation is $0.58775259. Available credit is not spending authorization.
Check pinned endpoint, price ceilings and account/key credit before admission.

This is a **one-attempt information-value screen**, with equal generation limits,
not equal realized spending or a proven equal-total-resource policy advantage.
Neither arm may reinvest savings into retries. The later policy study must give
always-acquire, never-acquire and retry/restart baselines a common total API and
local-execution envelope. No selector is trained in this screen.

## Outcomes and decision

Full repair requires both public and evaluator suites. Preserve every selected
cell, public false acceptance, invalid output, regression of previously passing
public cases, cost and missingness. Primary contrast: spectrum minus feedback
full-repair count over 24 selected cells per arm. Report all per-bug/per-draw
counts, paired wins/losses, and finite worst/best bounds over the full denominator.
No p-value, bootstrap, significance threshold or generalization claim is used for
these eight deliberately exposed, highly clustered bugs.

The development screen passes only with all 48 cells observed, at least three
distinct bugs repaired by spectrum in at least two of three draws, and a strictly
positive net spectrum advantage in **each of the three draws**. An incomplete
bank is inconclusive regardless of favorable observed cells. A complete negative
screen is retained. Passing permits designing an independent replication and
resource-matched policy comparison; it does not authorize automatic training.

Before dispatch: freeze exact prompts, source hashes, accounting and this
protocol; exclude overlap with historical planned/admitted request bodies; run
offline tests and verify CI on the exact source commit. After completion or
interruption: reconcile every receipt/reserve, verify prompt projections, replay
public/evaluator suites independently, export inert evidence, and report all
outcomes. The earlier 429 cause and historical charges remain unresolved even
if this new collection succeeds.
