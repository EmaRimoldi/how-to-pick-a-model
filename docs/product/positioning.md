# Positioning

AutoResearch Orchestration should be presented as an evaluation harness, not as another
multi-agent launcher.

## Core Thesis

Spawning more agents is easy. Measuring whether the extra agents improved the
outcome is the hard part.

The current evidence supports a narrow but useful claim:

> On the checked-in AutoResearch benchmark, a 62-attempt memory ablation found
> that shared memory reduced mean `val_bpb` from 1.816 to 1.049. Shared memory
> did not solve the task, but it made exploratory agents less destructive.

The repository also includes `uv run agent-workflow demo`, an offline fixture
that generates a Workflow Card and static HTML report without Claude Code, GPU,
or provider quota. Treat it as onboarding, not as scientific evidence.

## Audience

Primary:

- developers already using Claude Code worktrees or subagents;
- researchers studying agent orchestration and multi-agent evaluation;
- ML/AI platform teams deciding whether multi-agent workflows justify their
  extra cost.

Secondary:

- founders and devtool builders looking for a concrete agent-evaluation wedge.

## Naming Risk

`agent-workflow` is clear but generic. Before a coordinated launch, decide
whether to keep it or rename to something more searchable.

Potential naming directions:

- `AgentAblate`: emphasizes controlled ablations.
- `WorthIt`: emphasizes the decision question, but may be too broad.
- `AgentWorth`: explicit but less elegant.
- `WorkflowBench`: clearer benchmark framing, likely crowded.
- `MultiAgentEval`: descriptive and searchable, less brandable.

Do not rename casually. A rename should update the GitHub repository, package
name, CLI, badges, docs, landing page, and launch copy in one pass.

## Benchmark Roadmap

The biggest credibility gap is generality. AutoResearch/CIFAR-10 is a real
controlled substrate, but it is still one task.

Next benchmark candidates:

1. Coding patch task: a small SWE-Bench-Lite-style subset where agents modify
   code and tests define success.
2. Research synthesis task: agents answer paper or repo questions with cited
   evidence, scored by rubric.
3. Tool-use/repo-maintenance task: agents triage issues, update docs, or perform
   structured refactors with deterministic checks.

The launch claim should stay narrow until at least two additional substrates are
implemented and reported.
