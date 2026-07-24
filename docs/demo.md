# Offline Demo

The fastest way to inspect AutoResearch Orchestration is the offline demo:

```bash
uv run agent-workflow demo
```

This command does not invoke Claude Code, GPUs, SLURM, or external model
providers. It writes deterministic fixture data under `runs/` so reviewers can
inspect the artifact shape before running live agents.

## Generated Files

```text
runs/experiment_demo_.../
  config.json
  summary.json
  trajectories.csv
  workflow_card.md
  workflow_card.json
  report.md
  report.html
```

## What It Proves

The demo proves that the local CLI can generate a reviewable evidence bundle:

- one compact Workflow Card;
- one static HTML report;
- one machine-readable summary;
- one trajectory table shaped like live run output.

It does not prove that a live multi-agent workflow improved a real task. Use
`parallel`, `parallel-shared`, `swarm`, and `merge` modes for live evidence.

## Custom Output Directory

```bash
uv run agent-workflow demo --output-dir /tmp/agent-workflow-demo
```

Use `--experiment-id` for stable paths during screenshots or CI checks:

```bash
uv run agent-workflow demo \
  --output-dir /tmp/agent-workflow-demo \
  --experiment-id readme_demo
```
