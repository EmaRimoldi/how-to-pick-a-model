# Project Log

## 2026-04-21

### Benchmark Foundation

- Inspected the existing query-engine benchmark and reused the benchmark harness, verifier, scoring, workload generation, and reference engine.
- Created the project layout with `configs/`, `benchmarks/`, `src/vao/`, `scripts/`, `tests/`, `runs/`, and `artifacts/`.
- Implemented the canonical six-branch C(a) loop in `vao.orchestrator`, including isolated branch workspaces and top-1 promotion without counterfactual leakage.
- Added schemas, mode classification, estimator computation, and run validation.
- Landed deterministic `local_stub`, strict Claude CLI transport, OpenAI-compatible transport, OpenAI Responses transport, and Codex CLI transport.

### Protocol Hardening

- Added strict structured parsing, source validation, prompt snapshots, and prompt-control tests.
- Consolidated the active model-generation surface onto `src/vao/prompts/single_step_program.txt`.
- Kept `structured_edits` as the active edit protocol and retained `unified_diff` analysis tooling only for protocol comparison.
- Added feedback-use diagnostics for C(b) with controlled branch promotion.
- Added per-run diagnostics plots and summary generators for active experiment runs.

### Active Benchmark Surface

- Added the active dev/holdout profile split in `configs/profiles.yaml`.
- Added local smoke, local profile validation, prompt-controlled dev comparison, holdout evaluation, and one-step matrix configs.
- Validated prompt-controlled single-step smokes for GPT/Codex, Claude, and Qwen backends.
- Completed the first paper dev run with `gpt-5.3-codex-spark` across the three dev profiles.

### Repository Cleanup

- Removed superseded direct-edit paths, legacy prompt templates, and obsolete configs from the active experiment surface.
- Added `best_loss_by_step.png` to the per-run diagnostics so selected, step-best counterfactual, best-visible-so-far, and best-counterfactual-so-far loss trajectories are visible.
- Removed redundant plot folders for duplicate or non-current runs and refreshed the retained artifact catalog.
- Removed the legacy local training surface, auxiliary scripts, and derived artifacts that were outside the benchmark-only workflow.
