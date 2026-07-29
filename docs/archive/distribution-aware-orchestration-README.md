# Verifiable Agentic Optimization for AutoResearch Routing

> Historical source README. Paths below describe the former standalone tree.
> The `stateful_query_engine` directory now lives at
> `experiments/archive/stateful-query-engine/` because it contains no
> experimental result, report, or run evidence.

This repository contains the active benchmark harness and analysis code for
**verifiable agentic optimization on AutoResearch-style CIFAR-10 training
scripts**.

The active experimental question is now:

> given a concrete AutoResearch workload instance, can a deployment policy
> choose the most appropriate model or harness action using only cheap signals
> available before the expensive run?

The old source repository described QueryState / Stateful Query Engine as an
archive. The unified tree retains it only under `experiments/archive/`.

## Active benchmark surface

The active AutoResearch surface is consolidated under:

- `autoresearch/benchmark/cifar10/`
- `autoresearch/analysis/autoresearch_*`
- `autoresearch/configs/autoresearch_cifar10_*`
- `autoresearch/prompts/`
- `autoresearch/scripts/`
- `autoresearch/campaigns/`

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
- `resnet_micro`

These workload labels are properties of the editable starting program, not
action labels.

Current verifier budget:

- all three workloads default to **256 inner training steps** per verifier run

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
- `gpt_5_4`

## Quick start

### 1) Workload pilot campaign

```bash
PYTHONPATH=src:. ./.venv/bin/python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml \
  --models gpt_5_3_codex,gpt_5_4,gpt_5_4_mini \
  --workloads cnn_compact,mlp_flat,resnet_micro \
  --seeds 7001:2 \
  --split pilot
```

### 2) Workload holdout campaign

```bash
PYTHONPATH=src:. ./.venv/bin/python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_workload_holdout.yaml \
  --models gpt_5_3_codex,gpt_5_4,gpt_5_4_mini \
  --workloads cnn_compact,mlp_flat,resnet_micro \
  --seeds 8001:2 \
  --split holdout
```

### 3) Threshold / occupancy analysis on completed runs

```bash
PYTHONPATH=src:. ./.venv/bin/python -m autoresearch.analysis.autoresearch_cifar10_threshold_sweep \
  autoresearch/runs/workload_pilot autoresearch/runs/workload_holdout \
  --output autoresearch/artifacts/workload_threshold_report.json
```

## Main entry points

- `python -m autoresearch.analysis.autoresearch_cifar10_pilot --config autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml ...`
- `python -m autoresearch.analysis.autoresearch_cifar10_single_trajectory_campaign --config autoresearch/configs/autoresearch_cifar10_single_trajectory_campaign.yaml ...`
- `python -m autoresearch.analysis.autoresearch_cifar10_threshold_sweep autoresearch/runs/... --output autoresearch/artifacts/.../workload_threshold_report.json`

## SWE-bench orchestration scaffold

The experimental SWE-bench orchestration scaffold lives under:

- `swebench/studies/open_source_orchestration/`
- `swebench/studies/codex_suite_100_vs_gpt55/`
- `swebench/src/vao/swebench_orchestration/`

Small dev-slice run:

```bash
PYTHONPATH=src:swebench/src:swebench:. ./.venv/bin/python -m vao.swebench_orchestration.download \
  --dataset-name princeton-nlp/SWE-Bench_Verified \
  --split test \
  --limit 8 \
  --output-dir swebench/studies/open_source_orchestration/data/dev_slice

PYTHONPATH=src:swebench/src:swebench:. ./.venv/bin/python -m vao.swebench_orchestration.prompt \
  --config swebench/studies/open_source_orchestration/configs/swebench_orchestration_meta_design.yaml

PYTHONPATH=src:swebench/src:swebench:. ./.venv/bin/python -m vao.swebench_orchestration.analyze \
  --traces swebench/tests/fixtures/swebench_orchestration_traces.jsonl \
  --orchestration-design swebench/tests/fixtures/swebench_orchestration_design.json \
  --output swebench/studies/open_source_orchestration/runs/fixture_analysis/report.json
```

## Configs

Useful configs:

- `autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml`
- `autoresearch/configs/autoresearch_cifar10_workload_holdout.yaml`
- `autoresearch/configs/autoresearch_cifar10_single_trajectory_campaign.yaml`

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

In the former source tree, `Archive/stateful_query_engine/` contained the older
QueryState benchmark implementation. The current repository relocates those
files to `experiments/archive/stateful-query-engine/` and does not treat them as
active experimental evidence.
