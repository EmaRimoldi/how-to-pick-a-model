---
description: Preflight this repository for Agent Workflow, then plan a safe parallel Claude Code evaluation.
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# Evaluate Agent Workflow

Run a product-oriented preflight for this repository.

1. Run `uv run agent-workflow doctor`.
2. Use `workflow-reviewer` to inspect setup and safety boundaries.
3. Use `workflow-analyst` to identify the strongest existing evidence.
4. If, and only if, the user explicitly requested a live run, use
   `workflow-runner` for one bounded fixed-step smoke run.
5. Return a concise decision report:
   - what is ready;
   - what is blocked;
   - which workflow should be tested next;
   - exact command to run next.
