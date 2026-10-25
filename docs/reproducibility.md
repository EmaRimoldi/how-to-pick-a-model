# Reproducibility

The retained evidence is AutoResearch/CIFAR-10 and completed HumanEval+ studies.
The next state-conditioned policy experiment is specified in
[decision protocol](decision-protocol.md). A cost-bounded API pilot now has a
[separate protocol and runner](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md).

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
