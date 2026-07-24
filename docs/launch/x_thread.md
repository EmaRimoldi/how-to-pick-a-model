# X Thread Draft

```text
1/ I ran 62 Claude Code agent attempts to test one question:

Does shared memory actually help multi-agent search?
```

```text
2/ Result on the checked-in AutoResearch benchmark:

No memory: best val_bpb 0.933, mean 1.816
Shared memory: best val_bpb 0.914, mean 1.049

That is 42% lower mean validation loss in this substrate.
```

```text
3/ The honest interpretation:

Shared memory did not solve the task, but it made exploratory agents much less destructive.
```

```text
4/ Spawning agents is easy now.

Measuring whether parallelism, shared memory, or swarm coordination improved the result is the harder part.
```

```text
5/ So I packaged the experiment as AutoResearch Orchestration: an open-source harness for testing Claude Code agent teams before scaling them.
```

```text
6/ It lets you define a custom roster:

- explorer
- optimizer
- regularizer
- any N your quota/compute supports

Each agent can have its own role, model, memory mode, and device assignment.
```

```text
7/ The harness gives each agent an isolated workspace, runs fixed-step evaluation, and preserves configs, logs, trajectories, snapshots, metrics, and reports.
```

```text
8/ The checked-in benchmark is AutoResearch:

Claude Code agents edit a CIFAR-10 train.py and try to reduce validation bits-per-byte.

Lower val_bpb is better.
```

```text
9/ Quick start:

git clone https://github.com/EmaRimoldi/agent-workflow.git
cd agent-workflow
uv run agent-workflow demo
```

```text
10/ Repo:

https://github.com/EmaRimoldi/agent-workflow

I am looking for feedback from people building Claude Code, agent worktree, and multi-agent coding workflows.
```
