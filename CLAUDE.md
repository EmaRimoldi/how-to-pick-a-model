# How to Pick a Model: Claude Code Guide

How to Pick a Model combines the deployment-selection theory, AutoResearch
orchestration harness, and non-AutoResearch model-routing evidence. The
historical `agent-workflow` CLI remains the executable surface for the
AutoResearch orchestration track.

## Default Behavior

- Prefer read-only inspection unless the user explicitly asks for edits.
- Do not start live Claude Code agent experiments unless the user explicitly
  asks for a live run.
- Before any live run, execute `uv run agent-workflow doctor`.
- Use fixed-step evaluation for comparable claims:
  `--train-max-steps 1170 --serialized-evaluator`.
- Keep generated run artifacts under `runs/` and preserve `config.json`,
  logs, trajectory files, snapshots, and reports.
- Keep each experiment under its benchmark family in `experiments/`; use
  `autoresearch-cifar10`, `humaneval-plus`, `mbpp-plus`, `bbh`, or
  `swebench-verified` and give each bundle a question-specific name.

## Product Surface

- CLI: `uv run agent-workflow --help`
- Setup check: `uv run agent-workflow doctor`
- Single-agent baseline: `uv run agent-workflow single-long`
- Independent parallel agents: `uv run agent-workflow parallel`
- Shared-memory parallel agents: `uv run agent-workflow parallel-shared`
- Blackboard swarm: `uv run agent-workflow swarm`
- Post-run synthesis: `uv run agent-workflow merge`

## Safety Boundary

Live runs invoke the local `claude` binary and can edit files inside isolated
workspaces. Run them from a clean clone or disposable worktree, not from a
directory containing secrets or unrelated personal files.

Use the project subagents in `.claude/agents/` for planning, execution, and
analysis. They should report concise evidence and file paths rather than broad
claims.
