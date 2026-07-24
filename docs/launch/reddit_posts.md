# Reddit Drafts

Use these only where they fit the community. Do not cross-post the same text
unchanged everywhere.

## r/programming

```text
I ran a 62-attempt Claude Code agent experiment to test whether shared memory
actually helps multi-agent search, then packaged the harness as an open-source
repo.

The problem I am trying to solve: spawning more agents is now easy, but it is
hard to tell whether parallelism, shared memory, or coordination actually
improved the result.

Current checked-in result on the AutoResearch benchmark:

- no memory: best val_bpb 0.933, mean 1.816
- shared memory: best val_bpb 0.914, mean 1.049

That is a 42% lower mean validation loss in this substrate. The honest
interpretation is narrower: shared memory did not solve the task, but it made
exploratory agents less destructive.

AutoResearch Orchestration lets you define one agent or N agents, run them in isolated
workspaces, keep evaluation fixed-step, and preserve configs/logs/trajectories
for later review.

Repo:
https://github.com/EmaRimoldi/agent-workflow

I would appreciate feedback on the CLI/API surface and what evidence you would
want before trusting a multi-agent coding workflow.
```

## r/MachineLearning

```text
I built AutoResearch Orchestration, an open-source evaluation harness for Claude Code
agent teams.

The checked-in benchmark is an AutoResearch task where agents edit a CIFAR-10
training file and try to reduce validation bits-per-byte. The current strongest
signal is a 62-attempt memory ablation: shared memory did not solve the task,
but it reduced mean val_bpb from 1.816 to 1.049 and made exploratory agents less
destructive on this benchmark.

The repo includes fixed-step evaluation, agent trajectories, snapshots, logs,
and experiment summaries.

Repo:
https://github.com/EmaRimoldi/agent-workflow

I am interested in feedback on the evaluation protocol and whether this is a
useful substrate for reproducible agent-workflow experiments.
```

## r/ClaudeAI or agent-specific communities

```text
I built a small open-source harness for testing Claude Code agent teams:

- define one agent or N agents
- assign roles/models/memory modes/devices
- run isolated workers
- compare single, parallel, shared-memory, swarm, and merge workflows

Repo:
https://github.com/EmaRimoldi/agent-workflow

I would love feedback from people using Claude Code worktrees or subagents in
real projects.
```
