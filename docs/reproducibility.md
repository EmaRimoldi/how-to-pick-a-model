# Reproducibility

The retained evidence is AutoResearch/CIFAR-10 and completed HumanEval+ studies.
The state-conditioned policy question is specified in
[decision protocol](decision-protocol.md). A cost-bounded API pilot now has a
[separate protocol and runner](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md).
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
uv run agent-workflow demo --output-dir /tmp/how-to-pick-a-model-demo
make paper-figures-autoresearch
```

`make check` regenerates the inventory, knowledge, experiment, and command maps,
validates references and evidence structure, compiles Python, and runs unit tests.
The demo is deterministic fixture data; figure generation reads tracked results.
Neither launches live models or GPU training.

Optional profiles:

- `autoresearch`: Torch/Torchvision for CIFAR-10 verification.
- `other-experiments`: HumanEval+ worker/verifier and routing dependencies.
- `continuation-pilot`: EvalPlus for the API pilot, without requiring local LLM
  weights or Torch.
- `analysis-ml`: optional runtime diversity/embedding analysis dependencies.
- `all-experiments`: dependencies for the retained experiment surfaces.

Install only the profile needed, for example:

```bash
uv sync --dev --extra autoresearch --frozen
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

## AutoResearch evidence

The four retained bundles cover initial-model calibration, controlled evaluator
behavior, shared memory, and three-worker routing. The three-worker panel has
270 processed trajectories and 180 balanced raw traces; its bundle README is
authoritative about missing pilot coverage.

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed   --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json   --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Raw campaign archives remain under `artifacts/raw/` in Git LFS. Inventory sizes
use logical LFS object sizes for both pointer-only and hydrated checkouts.

## HumanEval+ evidence

The four retained bundles cover the model-size frontier, retry allocation,
strategy routing, and held-out router-context selection. Saved worker logs cover
164 tasks per model for the 1.5B, 7B, and 32B frontier.

```bash
uv run python -m src.load_traces   --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
```

Worker reruns require EvalPlus and the configured local models. Router reruns
may require model CLI/API access. Original cluster run/config snapshots are
provenance, not machine-independent launch commands.

## Runtime baselines and paper

The historical `agent-workflow` CLI remains for baseline execution,
instrumentation, and reports. Before an explicitly requested live run, use its
`doctor` command, fixed-step verification, and serialized evaluator controls.
Keep generated runs, usage, snapshots, and configs under ignored output paths.

```bash
make paper-build
```

This compiles both retained manuscripts with TeX Live into `/tmp/` and leaves the
source tree clean. Only referenced paper figures are vendored.

## Limits

Old traces cannot answer what a different model would have done from a checkpoint.
Live outputs vary with model/provider versions, context, sampling, and compute.
The historical manuscript accounting discrepancy remains documented in
[audit](audits/manuscript-reproducibility.md). Retired study paths and their full
history are documented in [repository history](history-merge.md).
