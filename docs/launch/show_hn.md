# Show HN Draft

Title:

```text
Show HN: I ran 62 Claude Code agent attempts to test whether shared memory helps
```

Body:

```text
Hi HN,

I built AutoResearch Orchestration after running a controlled Claude Code agent experiment:
does shared memory make multi-agent search better, or just more complicated?

The problem: it is now easy to spawn more agents, but hard to know whether
parallelism, shared memory, or swarm coordination actually improved the result.

The first checked-in result is a 62-attempt memory ablation on a CIFAR-10
AutoResearch task:

- no memory: best val_bpb 0.933, mean 1.816
- shared memory: best val_bpb 0.914, mean 1.049

That is a 42% lower mean validation loss in this substrate. The honest
interpretation: shared memory did not solve the task, but it made exploratory
agents much less destructive.

AutoResearch Orchestration lets you:

- define one agent or N agents with roles, models, memory mode, and CPU/GPU assignment
- run isolated Claude Code workers against the same task
- keep evaluation fixed-step so hardware contention does not distort the comparison
- preserve configs, logs, trajectories, snapshots, and reports

Quick start:

git clone https://github.com/EmaRimoldi/agent-workflow.git
cd agent-workflow
uv run agent-workflow demo

Repo:
https://github.com/EmaRimoldi/agent-workflow

I would be especially interested in feedback from people running Claude Code,
agent worktrees, or multi-agent coding workflows in practice.
```
