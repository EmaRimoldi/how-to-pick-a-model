# Claude Code Orchestration

AutoResearch Orchestration is productized around a narrow use case: help a team design and
score a Claude Code agent workflow before spending serious time or quota on it.

The repository is open-source and runs locally. Live Claude Code runs still
depend on the user's subscription, provider quota, and available CPU/GPU
resources.

## Landscape

This space already has useful infrastructure:

- Anthropic documents parallel Claude Code sessions with git worktrees and
  notes that worktrees isolate file edits while subagents coordinate work:
  <https://code.claude.com/docs/en/worktrees>.
- Anthropic's subagent docs describe separate agent instances with isolated
  context, parallel execution, specialized prompts, and tool restrictions:
  <https://code.claude.com/docs/en/agent-sdk/subagents>.
- Community projects such as `parallel-worktrees`, `awesome-claude-code-subagents`,
  `claude-sub-agent`, and broad agent marketplaces provide agent templates,
  worktree helpers, and development workflows.

The gap is measurement. Most tools help users run more agents. AutoResearch Orchestration
asks whether the additional agents actually improved the result, and lets users
define their own agent roster instead of accepting a fixed demo topology.

## Product Wedge

AutoResearch Orchestration gives Claude Code a controlled evaluation loop:

1. Spawn isolated workers for the same task.
2. Configure one agent or N agents with explicit roles, models, memory modes,
   and CPU/GPU assignment.
3. Run single-agent, parallel, shared-memory, swarm, or merge workflows.
4. Keep evaluation fixed-step so hardware contention does not masquerade as
   model quality.
5. Collect trajectories, snapshots, logs, and validation metrics.
6. Report whether the added coordination improved quality enough to justify
   the cost.

That makes the product less like a generic agent launcher and more like a
pre-flight evaluation system for agent architectures.

## Claude Code Surface

The repository includes:

- `CLAUDE.md`: always-on project instructions for Claude Code.
- `.claude/agents/workflow-runner.md`: bounded execution agent.
- `.claude/agents/workflow-analyst.md`: evidence-analysis agent.
- `.claude/agents/workflow-reviewer.md`: product/reproducibility reviewer.
- `.claude/commands/evaluate-agent-workflow.md`: one-shot preflight command.
- `uv run agent-workflow doctor`: local readiness check.

## Recommended Flow

```bash
uv sync --dev --frozen
uv run agent-workflow demo
uv run agent-workflow doctor
uv run agent-workflow parallel --help
uv run agent-workflow parallel-shared --help
uv run agent-workflow swarm --help
```

`agent-workflow demo` is an offline fixture. It previews the evidence bundle
shape before a user spends Claude Code quota or evaluator compute.

For live tests, use fixed-step settings:

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

For custom agent teams, use the roster schema:

```bash
uv run agent-workflow parallel-shared \
  --config configs/agent_roster_example.yaml \
  --experiment-id custom_roster_smoke
```

Each roster entry can set `id`, `role`, `model`, `temperature`, `cuda_device`,
time budget, train budget, and memory flags. `N` is bounded by provider limits,
subscription limits, evaluator concurrency, and local compute, not by a hardcoded
two-agent assumption.

## Positioning

Short version:

> AutoResearch Orchestration helps AI teams stop guessing which agent architecture to run.

More explicit version:

> AutoResearch Orchestration is a Claude Code evaluation harness that tests whether
> memory, parallelism, or swarm coordination improves an agent workflow before
> a team spends real money running it.
