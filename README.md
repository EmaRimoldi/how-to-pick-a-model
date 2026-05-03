# Verifiable Agentic Optimization for AutoResearch Routing

This repository contains the active benchmark harness and analysis code for
**verifiable agentic optimization on AutoResearch-style CIFAR-10 training
scripts**.

The active experimental question is now:

> given a concrete AutoResearch workload instance, can a deployment policy
> choose the most appropriate model or harness action using only cheap signals
> available before the expensive run?

The old QueryState / Stateful Query Engine benchmark has been archived under
`Archive/stateful_query_engine/` and is no longer part of the active mainline.

## Active benchmark surface

The active benchmark lives under:

- `benchmarks/autoresearch_cifar10/`
- `src/vao/analysis/autoresearch_*`
- `configs/autoresearch_cifar10_*`

A task instance is a concrete AutoResearch run consisting of:

- an initial editable `train.py`
- a fixed training/evaluation budget
- a verifier based on validation loss
- a data/training regime
- a nuisance seed

## Workload family

The active mainline no longer relies on hand-crafted bottleneck labels.  The
benchmark treats **AutoResearch itself** as the task family and instantiates it
on three realistic CIFAR-10 workloads that share the same verifier and metric
but start from different architectures:

- `cnn_compact`
- `mlp_flat`
- `resnet_tiny`

These workload labels are properties of the editable starting program, not
action labels.

Current verifier budget:

- all three workloads default to **128 inner training steps** per verifier run

## Active protocol

The paper-facing protocol is **task-level model routing**:

1. a router observes cheap live signal `Z` before a full run
2. it chooses one model or subagent from a small menu
3. that chosen model performs the whole AutoResearch trajectory
4. holdout analysis compares:
   - best single model
   - workload-only deployment policy
   - workload + probe router
   - per-instance oracle router

The current default model menu is:

- `gpt_5_4_mini`
- `gpt_5_3_codex`
- `claude_sonnet`

## Quick start

### 1) Local deterministic smoke

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.orchestrator \
  --config configs/autoresearch_cifar10_workload_local_smoke.yaml \
  --steps 1 \
  --run-id autoresearch_workload_smoke
```

### 2) Workload pilot campaign

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.analysis.autoresearch_cifar10_pilot \
  --config configs/autoresearch_cifar10_workload_pilot.yaml \
  --models gpt_5_4_mini,gpt_5_3_codex,claude_sonnet \
  --workloads cnn_compact,mlp_flat,resnet_tiny \
  --seeds 7001:2 \
  --split pilot
```

### 3) Workload holdout campaign

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.analysis.autoresearch_cifar10_pilot \
  --config configs/autoresearch_cifar10_workload_holdout.yaml \
  --models gpt_5_4_mini,gpt_5_3_codex,claude_sonnet \
  --workloads cnn_compact,mlp_flat,resnet_tiny \
  --seeds 8001:2 \
  --split holdout
```

### 4) Threshold / occupancy analysis on completed runs

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.analysis.autoresearch_cifar10_threshold_sweep \
  runs/autoresearch_cifar10/workload_pilot runs/autoresearch_cifar10/workload_holdout \
  --output artifacts/autoresearch_cifar10/workload_threshold_report.json
```

## Main entry points

- `python -m vao.orchestrator --config configs/autoresearch_cifar10_workload_local_smoke.yaml --steps 1 --run-id autoresearch_workload_smoke`
- `python -m vao.analysis.autoresearch_cifar10_pilot --config configs/autoresearch_cifar10_workload_pilot.yaml ...`
- `python -m vao.analysis.autoresearch_cifar10_single_trajectory_campaign --config configs/autoresearch_cifar10_single_trajectory_campaign.yaml ...`
- `python -m vao.analysis.autoresearch_cifar10_threshold_sweep runs/... --output artifacts/.../workload_threshold_report.json`

## Configs

Useful configs:

- `configs/autoresearch_cifar10_workload_local_smoke.yaml`
- `configs/autoresearch_cifar10_workload_pilot.yaml`
- `configs/autoresearch_cifar10_workload_holdout.yaml`
- `configs/autoresearch_cifar10_single_trajectory_campaign.yaml`

## Paper LaTeX submodule

The Overleaf LaTeX project is tracked as a Git submodule at `paper_overleaf`.
After cloning on a new machine, initialize it with:

```bash
git submodule update --init --recursive
```

To edit or sync the paper, work inside the submodule:

```bash
cd paper_overleaf
git pull
git status
```

Commits made inside `paper_overleaf` push to the Overleaf remote. After
updating the paper submodule, return to this repository and commit the changed
submodule pointer.

## Archive

Archived material is preserved under `Archive/`.

- `Archive/stateful_query_engine/` contains the older QueryState / Stateful
  Query Engine benchmark, configs, artifacts, and theorem-facing analysis code.

Use the archive only for historical comparison or reproduction of the older
experiments; do not treat it as the active benchmark surface.
