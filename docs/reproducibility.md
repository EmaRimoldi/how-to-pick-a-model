# Reproducibility

The seven retained studies cover HumanEval+, MBPP+ and BigCodeBench coding tasks.
The state-conditioned policy question is specified in
[decision protocol](decision-protocol.md). The initial API pilot is archived with
[billing, configuration and task-exclusion provenance](../experiments/humaneval-plus/context-value/provenance/continuation-pilot/README.md).
The subsequent [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md)
uses the same optional environment and billing/isolation controls, with separate
code/feedback conditions and saved prospective forecasts.
The [frozen recovery protocol](../experiments/humaneval-plus/context-value/VALIDATION.md)
adds a trained one-checkpoint selector and a task-disjoint producer-transfer
evaluation. Its saved-data analyzer requires no credentials, GPU or candidate
execution. Optional EvalPlus is needed for new collection, not for replaying
recorded results.

## Safe environment and checks

```bash
uv sync --dev --frozen
make check
```

`make check` regenerates the inventory, knowledge, experiment, and command maps,
validates references and evidence structure, compiles Python, and runs unit tests.
These checks make no live model calls or GPU training runs.

Optional profiles:

- `other-experiments`: HumanEval+ worker/verifier and routing dependencies.
- `continuation-pilot`: EvalPlus for the API pilot, without requiring local LLM
  weights or Torch.
- `all-experiments`: dependencies for the retained experiment surfaces.

Install only the profile needed, for example:

```bash
uv sync --dev --extra other-experiments --frozen
```

Read the command safety manifest before unfamiliar scripts. Live model, provider,
cluster, or training runs require explicit authorization and an isolated workspace.

## Recorded recovery replay

```bash
uv run python scripts/analyze_recovery_validation.py \
  --input experiments/humaneval-plus/context-value/results/validation-20261022 \
  --output runs/recovery-reanalysis
```

Use a fresh output directory. The analyzer reads the saved prompts, observations,
policy weights and billing journal; it does not contact a provider or run candidate
programs. It refits the development policy as an integrity check, validates the
prospective forecast boundary and reconstructs finite budgeted rollouts. Outputs
include JSON, Markdown, a PNG and a vector PDF. Scalar estimates are deterministic;
CPU microbenchmarks and figure metadata can differ across machines.

The bundle's `checksums.json` records curated-file integrity. Account balances and
credentials are omitted. Six unknown transport admissions retain their full cost
reservation; seven explicit empty provider errors use disclosed policy-backed zero
charges. Deployment outage/retry cost remains incompletely identified. See the
[blog](blog/when-to-keep-failed-code.md) and [protocol amendments](../experiments/humaneval-plus/context-value/VALIDATION.md)
for the producer substitution and claim boundaries.

Fresh collection additionally needs `--extra continuation-pilot`, explicit
live/budget arguments and a new output path. Default planning makes no model
calls. The original and amended configs remain separate; no account key belongs
in a config, command argument or tracked file.

## Cross-benchmark replication

The [MBPP+ replication protocol](../experiments/mbpp-plus/context-value-transfer/PROTOCOL.md)
uses the same optional EvalPlus environment and macOS sandbox. Its former
HumanEval+ evaluation data are now explicitly training data. Live collection
shares the existing cumulative $2 cap and never retries unknown paid requests
automatically. Its separate offline analyzer executes no candidate code.

The [audited results](../experiments/mbpp-plus/context-value-transfer/results/replication-20261022/README.md)
retain 2,878 recovery responses, two censored solver cells and all 288 API
forecasts. All 96 selected states remain represented; complete-case comparisons
use 94 and are descriptive. The result README gives a command with
`--expected-analysis` to compare recomputed statistics with the published report,
in addition to checking raw journals and provenance. No optional EvalPlus
installation is needed for this replay.

Build the [separate empirical paper](../paper/recovery-value/README.md) with
TeX Live and a fresh output directory:

```bash
uv run python paper/recovery-value/build.py \
  --output /tmp/how-to-pick-a-model-recovery-paper
```

It reproduces the recorded analysis before generating tables and figures, then
compiles three times out of tree. Known campaign charges plus every unresolved
reservation total $1.39600335 under the original $2 cap; collection is finished.

## Feedback-only fixed policies on new tasks

The [BigCodeBench protocol](../experiments/bigcodebench/feedback-only-routing/PROTOCOL.md)
uses 157 reference-qualified, previously unqueried tasks and no new selector.
Collection is complete: 628 policy outcomes, 1,492 responses, $0.38896675 known
charges and zero unresolved reservations. The primary gate does not pass.
Reproduce all published figures' numerical inputs, final comparisons, receipt
and prompt audits, source hashes and the exact preserved interim snapshot:

```bash
uv run python scripts/verify_feedback_evidence.py \
  --input experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022
```

This reads data only: no credentials, candidate execution, optional EvalPlus,
model calls or Git history are required. Ten inert source snapshots are bound
to the actual collection commit `d65fbde`; they remain immutable when current
runtime code is maintained. Verification compares the saved snapshots, then
reconstructs recorded statistics with the current analysis implementation. The verifier-repeat source is a
separate postcollection diagnostic. The final report discloses one directly
requested interim look at 83 already completed tasks and its selection bias.
Original labels remain primary after the zero-discrepancy offline repeat.
Read the [complete report](../experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022/report.md)
and [research note](blog/feedback-only-escalation.md).

The completed collector must not be restarted. For inspection only:
Planning validates the pinned tasks and reference qualification, reports current
source drift from the historical freeze, and makes no provider call:

```bash
.venv/bin/python scripts/run_feedback_routing.py \
  --config experiments/bigcodebench/feedback-only-routing/configs/evaluation.json
```

Execution rejects any source drift before provider access. The historical freeze
therefore cannot be used to launch modified code; a future study needs a new
reviewed freeze and authorization. Original collection additionally required macOS sandbox-exec, the optional EvalPlus
profile for the isolation probe, a clean committed freeze, a fresh ignored
output directory, explicit `--execute`, and a key on un-echoed stdin. Its recorded
$4.00 collection ceiling belonged to a separate $5 authorization; neither that
completed collection nor the completed $2 campaign may be resumed. No uncertain call is retried.
`scripts/analyze_feedback_routing.py` audits saved receipts/messages without
provider calls; it refuses treatment analysis before `summary.json` exists.

## Archived CIFAR-10 material

CIFAR-10 calibration/routing experiments, raw archives and their dedicated
launcher/harness are removed from the current package. Complete sources and
historical data remain available through [provenance](history-merge.md).
Embedded manuscript figures remain vendored so the historical documents compile.

## HumanEval+ evidence

The four retained bundles cover the model-size frontier, retry allocation,
strategy routing, and held-out router-context selection. Saved worker logs cover
164 tasks per model for the 1.5B, 7B, and 32B frontier.

```bash
uv run python -m vao.humaneval.load_traces   --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
```

Worker reruns require EvalPlus and the configured local models. Router reruns
may require model CLI/API access. Original cluster run/config snapshots are
provenance, not machine-independent launch commands.

## Historical manuscripts

```bash
make paper-build
```

This compiles both retained manuscripts with TeX Live into `/tmp/` and leaves the
source tree clean. Only referenced paper figures are vendored. CIFAR-10 figures are archival
assets; their experiment sources are recovered from the provenance tag.

## Limits

Old traces cannot answer what a different model would have done from a checkpoint.
Live outputs vary with model/provider versions, context, sampling, and compute.
The historical manuscript accounting discrepancy remains documented in
[audit](audits/manuscript-reproducibility.md). Retired study paths and their full
history are documented in [repository history](history-merge.md).
