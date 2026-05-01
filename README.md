# Verifiable Agentic Optimization for AutoResearch Routing

This repository contains the active benchmark harness and analysis code for
**verifiable agentic optimization on AutoResearch-style CIFAR-10 training
scripts**.

The active experimental question is:

> given a concrete AutoResearch task instance, can a router choose the most
> appropriate model for the full run using only cheap live signals available at
> the start of the run?

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
- a seed / nuisance draw

Task modes are **latent classes of task instances** that share a
solver-relevant bottleneck. The current mainline uses six practitioner-friendly
modes:

- `lr-sensitive`
- `regularization-sensitive`
- `optimizer-sensitive`
- `data-skew-sensitive`
- `capacity-sensitive`
- `schedule-sensitive`

These are properties of instances, not action labels.

Current verifier budgets:

- short modes (`lr-sensitive`, `regularization-sensitive`, `optimizer-sensitive`, `data-skew-sensitive`): **128 training steps**
- long modes (`capacity-sensitive`, `schedule-sensitive`): **512 training steps**

## Active protocol

The paper-facing protocol is **task-level model routing**:

1. a router observes a live signal `Z` at the start of the run
2. it chooses one model from a small menu
3. that chosen model runs the full AutoResearch trajectory
4. holdout analysis compares:
   - best single model
   - learned router
   - oracle router

The current main horizon is **H=24** full-run optimization steps, with planned
ablations around smaller and larger horizons.

The active model menu prioritizes Codex-family and Claude-family models.

## Quick start

### 1) Local deterministic smoke

```bash
PYTHONPATH=src:. python -m vao.orchestrator \
  --config configs/autoresearch_cifar10_local_smoke.yaml \
  --steps 1 \
  --run-id autoresearch_cifar10_smoke
```

### 2) Task-mode pilot campaign

```bash
PYTHONPATH=src:. python -m vao.analysis.autoresearch_cifar10_pilot \
  --config configs/autoresearch_cifar10_pilot.yaml \
  --models gpt_5_4_mini,gpt_5_3_codex,gpt_5_3_codex_spark,claude_sonnet \
  --families lr-sensitive,regularization-sensitive,optimizer-sensitive,data-skew-sensitive,capacity-sensitive,schedule-sensitive \
  --seeds 7001:2 \
  --split pilot
```

### 3) Task-level model-routing summary

```bash
PYTHONPATH=src:. python -m vao.analysis.autoresearch_cifar10_model_routing \
  runs/autoresearch_cifar10/task_mode_pilot \
  --output artifacts/autoresearch_cifar10/model_routing_report.json
```

### 4) Smoke-test the declared model menu

```bash
PYTHONPATH=src:. python scripts/smoke_test_model_menu.py \
  --config configs/autoresearch_cifar10_model_routing_smoke.yaml \
  --output artifacts/autoresearch_cifar10/model_menu_smoke.json
```

## Main entry points

- `python -m vao.orchestrator --config configs/autoresearch_cifar10_local_smoke.yaml --steps 1 --run-id autoresearch_cifar10_smoke`
- `python -m vao.analysis.autoresearch_cifar10_pilot --config configs/autoresearch_cifar10_pilot.yaml ...`
- `python -m vao.analysis.autoresearch_cifar10_model_routing runs/... --output artifacts/.../model_routing_report.json`
- `python scripts/smoke_test_model_menu.py --config configs/autoresearch_cifar10_model_routing_smoke.yaml --output artifacts/.../model_menu_smoke.json`

## Configs

Useful configs:

- `configs/autoresearch_cifar10_local_smoke.yaml`
- `configs/autoresearch_cifar10_pilot.yaml`
- `configs/autoresearch_cifar10_model_routing.yaml`
- `configs/autoresearch_cifar10_model_routing_smoke.yaml`
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
