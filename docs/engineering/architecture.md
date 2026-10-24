# Runtime and evidence architecture

The maintained workflow separates experiment collection from analysis of recorded
evidence. It uses one implementation per operation; the two runtime packages serve
different retained experiments rather than competing implementations of a controller.
A general state-conditioned continue/restart/switch/stop controller remains future work.

```text
frozen tasks + protocol + model/budget settings
  -> vao.decisions collector
  -> provider receipts + budget journal + public verification + evaluator labels
  -> immutable experiment evidence + collection-source snapshots
  -> scripts/analyze_* and verify_feedback_evidence.py
  -> audited comparisons, reports and paper inputs

historical agent-workflow CLI
  -> agent_workflow modes / orchestrator / merger
  -> isolated AutoResearch workspaces, traces and baseline reports
```

## Verified task experiments

`src/vao/` owns verified execution, model adapters, run schemas and workspaces.
Within `vao.decisions`, `openrouter.py` owns provider accounting and conservative
budget reservations. `verification.py` and `bigcode.py` isolate candidate execution
and keep public feedback separate from evaluator-only labels. A public pass ends
a feedback-only trajectory even if hidden tests subsequently fail.

The collectors remain distinct where their scientific interventions differ:

| Surface | Responsibility |
| --- | --- |
| `pilot.py`, `context_value.py` | HumanEval+ checkpoint collection and code/feedback ablations |
| `recovery.py`, `recovery_policy.py`, `recovery_import.py` | Frozen recovery selection, replay and provenance |
| `transfer*.py` | MBPP+ replication and prospective forecasts |
| `feedback_routing.py` | BigCodeBench fixed feedback-only policies and shared initial responses |

These studies share transport, accounting and verification primitives. They do
not pool task holdouts, campaign budgets or reported comparisons. Defaults still
enforce the historical $2 campaign ceiling; the separately frozen BigCodeBench
collector must explicitly request its higher maximum. Unknown admissions remain
reserved and are never silently retried.

Entry points under `scripts/` invoke these collectors or analyze their journals.
Read the [decision protocol](../decision-protocol.md) and each experiment's freeze
before extending a collector. No collection command is part of normal CI.

## Historical AutoResearch baselines

`src/agent_workflow/` retains the `agent-workflow` CLI, baseline configuration,
snapshotting, reasoning traces, shared memory, diversity analysis and reporting.
Its parallel, shared-memory, single-agent, merge and swarm modes are baseline
execution tools. `agent_workflow.orchestrator.Orchestrator` manages their isolated
workspaces; it is not the orchestrator for the separate VAO task studies.

The installed CLI dispatches only to packaged modules. Merge options and execution
live in `agent_workflow.modes.merge`; `scripts/run_merge_phase.py` is a thin
compatibility entry point to that same implementation. Actual merge evaluation
still requires the documented external workspace and compute setup.

`autoresearch/` supplies the CIFAR-10 benchmark and processed-evidence analysis.
Root `src/*.py` modules retain the HumanEval+ baseline trace/routing analyses.
They are repository research entry points, not a second packaged CLI.

## Evidence and maintenance

`experiments/` contains protocols, configurations and curated results needed to
audit the recorded claims. Inert collection-source snapshots are intentional
provenance, not alternative runtime modules. Offline verification hashes those
snapshots and reconstructs receipts, prompt chains and statistics with maintained
analysis code. Compatible source maintenance does not invalidate past evidence;
changed scientific outputs or corrupted snapshots still fail verification.

Live collection is stricter: current task, qualification and source hashes must
match its frozen configuration. Plan-only inspection reports source drift without
calling a provider. A completed study is not permission to resume its collection.

The active manuscript sources remain separate. The abandoned SAI-3 theory line
is retained in Git history, not mixed into current empirical protocols; see the
[branch review](../audits/branch-consolidation.md).

Use [reproducibility](../reproducibility.md) for installation, saved-data replays,
optional dependencies and live-run prerequisites. `make check` regenerates the
navigation maps, checks readiness, compiles source and runs the offline suite.
