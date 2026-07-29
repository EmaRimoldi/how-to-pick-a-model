# Reproducibility Setup

This repo can be used at three levels:

1. Inspect checked-in experiment summaries, tables, and figures without running agents.
2. Regenerate reader-facing figures from processed result JSON.
3. Generate an offline demo bundle without Claude Code or GPU.
4. Run local smoke tests for the runtime and analysis code.
5. Re-run agent experiments with Claude Code and the AutoResearch substrate.

Historical experiment summaries are tracked evidence bundles. New agent runs will
not be bit-for-bit identical because Claude Code, model routing, service
versions, and stochastic agent decisions can change over time. For serious
reruns, pin the model, use fixed-step evaluation, and keep the generated run
directory.

## Requirements

- Python 3.10 or newer.
- `uv`.
- Git.
- `claude` CLI from Claude Code, authenticated and available on `PATH`.
- Network access for the first CIFAR-10 data download.

Install base Python dependencies:

```bash
uv sync --dev --frozen
```

`uv.lock` is committed and is the source of locked Python package versions. The
local `.venv/` directory is intentionally ignored; recreate it with `uv` rather
than committing it.

Install optional experiment profiles only when needed:

```bash
uv sync --dev --extra autoresearch --frozen    # torch/torchvision for CIFAR-10
uv sync --dev --extra swebench --frozen        # datasets/docker/swebench
uv sync --dev --extra analysis-ml --frozen     # scipy/sentence-transformers/torch
uv sync --dev --extra all-experiments --frozen # all optional profiles
```

## AutoResearch Model-Routing Reproduction

The AutoResearch model-routing results live under
`experiments/autoresearch-cifar10/three-worker-model-routing/`. The runnable infrastructure lives
under:

- `autoresearch/benchmark/cifar10/`: CIFAR-10 benchmark, workload templates,
  verifier wrapper, and source validation.
- `autoresearch/configs/`: active H=20 configs using `gpt_5_3_codex`,
  `gpt_5_4`, and `gpt_5_4_mini`.
- `autoresearch/prompts/`: model-generation and router prompts.
- `autoresearch/analysis/`: pilot, threshold, routing, and accounting modules.
- `autoresearch/scripts/`: plotting, artifact, Slurm, and campaign helpers.
- `src/vao/`: compatibility runtime used by the AutoResearch harness.

Verify the code without launching live agents or rerunning CIFAR-10 campaigns:

```bash
uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
```

Regenerate compact figures from the processed analysis JSON:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/agent_workflow_autoresearch_reproduced
```

Render the workload/action catalog:

```bash
uv run python -m autoresearch.analysis.autoresearch_cifar10_mode_catalog \
  --out-dir /tmp/agent_workflow_autoresearch_catalog
```

Full reruns require the `autoresearch` extra, authenticated model access, and
enough compute for CIFAR-10 verification. A minimal local-stub smoke run should
use tiny training budgets before launching any live campaign:

```bash
uv sync --dev --extra autoresearch --frozen
uv run python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml \
  --models autoresearch_local_stub \
  --workloads cnn_compact \
  --seeds 7001:1 \
  --steps 1 \
  --max-train-steps 2 \
  --output-root /tmp/agent_workflow_autoresearch_smoke
```

Historical raw workspaces, scheduler logs, and verifier intermediate
directories are not committed. The repo tracks processed accounting, figures,
and a minimal raw bundle for traceability.

## Repository File Audit

The file audit covers all committed source and experiment categories:

| Top-level area | Count | Reproducibility check |
| --- | ---: | --- |
| `experiments/` | 2,014 | parsed JSON/JSONL/CSV files; checked raw coverage manifests; reviewed each experiment README |
| `src/` | 99 | parsed imports against `pyproject.toml` base and optional dependency profiles; ran tests |
| `docs/` | 31 | checked setup commands, CLI commands, and experiment rerun paths |
| `tests/` | 30 | executed with `uv run pytest tests -q` |
| `scripts/` | 12 | checked imports and exercised non-live figure/report commands where safe |
| `autoresearch/` | 59 | benchmark, analysis, configs, prompts, scripts, and lightweight substrate; mapped Torch/Torchvision to the `autoresearch` extra |
| `prompts/` | 6 | live-agent prompt inputs |
| `.github/` | 5 | checked CI installs with `uv sync --dev --frozen` and runs `pytest` |
| `.claude/` | 4 | Claude Code project agents/commands |
| `configs/` | 7 | checked live-run config paths, backend aliases, and documented required external tools |
| top-level metadata | 7 | checked license, lockfile, package metadata, env template, and README |

No tracked `.venv/`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, `.env`,
private key, or credential file was found. Local `.venv/`, cache directories,
and OS metadata may exist on this machine, but they are ignored and are not
required to be committed.

Prepare the AutoResearch data:

```bash
cd autoresearch
uv run python prepare.py
cd ..
```

Run local smoke checks:

```bash
uv run agent-workflow demo --experiment-id readme_demo
uv run agent-workflow doctor
uv run pytest tests -q
uv run agent-workflow --help
```

`agent-workflow demo` writes deterministic fixture data under
`runs/experiment_readme_demo/`, including `report.html`, `workflow_card.md`,
`workflow_card.json`, `summary.json`, and `trajectories.csv`. It is useful for
reviewing artifact shape before running live agents, but it is not live Claude
Code evidence.

## Claude Code Setup

AutoResearch Orchestration invokes Claude Code headlessly through the `claude` binary. The
current runner builds commands in this shape:

```bash
claude \
  --print \
  --output-format json \
  --dangerously-skip-permissions \
  --model <model> \
  --system-prompt <system-prompt> \
  "<turn message>"
```

The exact call site is `src/agent_workflow/agents/claude_agent_runner.py`.

Install Claude Code using Anthropic's current setup instructions:

- Official setup docs: <https://code.claude.com/docs/en/setup>
- CLI reference: <https://code.claude.com/docs/en/cli-reference>

Common install paths as of July 2026:

```bash
# macOS, Linux, WSL
curl -fsSL https://claude.ai/install.sh | bash

# macOS with Homebrew stable channel
brew install --cask claude-code
```

Verify the install and auth state:

```bash
claude --version
claude doctor
claude auth status
```

If not authenticated, run:

```bash
claude auth login
```

## Claude Code Project Agents

This repository includes project-level Claude Code instructions and sub-agent
templates:

- `CLAUDE.md`: always-on project rules and safety boundaries.
- `.claude/agents/workflow-runner.md`: bounded execution of one preflight or
  experiment.
- `.claude/agents/workflow-analyst.md`: evidence review over runs, summaries,
  and figures.
- `.claude/agents/workflow-reviewer.md`: product and reproducibility review.
- `.claude/commands/evaluate-agent-workflow.md`: one-shot setup/evidence
  command for Claude Code.

Claude Code can run sessions in git worktrees so independent workers do not edit
the same files. AutoResearch Orchestration also creates isolated workspaces for live
experiments; use the built-in `doctor` check before launching them:

```bash
uv run agent-workflow doctor
```

## Safety Boundary

The runtime uses `--dangerously-skip-permissions` because experiments need
unattended file edits and shell commands inside isolated agent workspaces. Do not
run reviewer experiments from a directory containing secrets, production config,
or unrelated personal files.

Recommended practice:

- Run from a clean clone or disposable worktree.
- Keep `.env` local and never commit credentials.
- Review generated `runs/` artifacts before sharing.
- Do not grant Claude Code access to parent directories that are not part of the
  experiment.

## Minimal Agent Smoke Run

After local tests succeed and Claude Code is authenticated, start with a short run:

```bash
uv run agent-workflow single-long \
  --config configs/experiment.yaml \
  --time-budget 10 \
  --train-budget 120 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_single_long
```

For a matched parallel run:

```bash
uv run agent-workflow parallel \
  --config configs/experiment.yaml \
  --time-budget 10 \
  --train-budget 120 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_parallel
```

For shared-memory parallel mode:

```bash
uv run agent-workflow parallel-shared \
  --config configs/experiment.yaml \
  --time-budget 10 \
  --train-budget 120 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_parallel_shared
```

For a custom roster with different roles, models, temperatures, and devices:

```bash
uv run agent-workflow parallel-shared \
  --config configs/agent_roster_example.yaml \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_custom_roster
```

The config file controls `agents.roster`. Each entry becomes one Claude Code
worker. The maximum useful `N` depends on Claude Code/account limits, provider
rate limits, evaluator concurrency, and available local CPU/GPU capacity.

The swarm command currently has a separate surface:

```bash
uv run agent-workflow swarm --blackboard-dir /tmp/agent-workflow-blackboard
uv run agent-workflow swarm --run --config configs/experiment.yaml --time-budget 10 --train-budget 120 --n-agents 2
```

## Reviewer-Grade Settings

Use these settings when the output will support a claim:

- `--train-max-steps 1170` so the evaluator is fixed-step rather than
  time-based.
- `--serialized-evaluator` when multiple agents share a machine.
- A pinned Claude model in `configs/experiment.yaml`.
- A pre-registered `--target-val-bpb` when computing certified hitting time.
- A clean `--experiment-id` that names the experiment and date.

Example:

```bash
uv run agent-workflow parallel \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --target-val-bpb 0.824 \
  --success-confidence 0.80 \
  --experiment-id study06_parallel_d01
```

## Output To Preserve

Agent runs write under `runs/` by default. Preserve at least:

- `config.json`
- per-agent `logs/`
- `results/trajectory.jsonl`
- `results/results.tsv`
- `results/training_runs.jsonl`
- `results/snapshots/`
- aggregate reports

These files are what make later certified-time, diversity, and decomposition
analysis auditable.

## Experiment Reproduction Matrix

The per-experiment commands and limits are documented in
[`experiments/reproducibility.md`](../experiments/reproducibility.md). Use that
matrix to distinguish:

- figures/tables that can be regenerated from tracked files;
- local reruns that require `torch`, `datasets`, Docker, or SWE-bench extras;
- historical live-agent results that cannot be reproduced bit-for-bit because
  raw workspaces, provider state, or model services are external.
