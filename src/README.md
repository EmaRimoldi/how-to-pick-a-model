# Source Code Map

This directory contains three code surfaces that come from different historical
tracks. Keep their responsibilities separate.

## `agent_workflow/`

Runtime and CLI compatibility surface for AutoResearch Orchestration.

Important entrypoints:

- `agent_workflow/cli.py`: `agent-workflow` command dispatch.
- `agent_workflow/launcher.py`: legacy live-run launcher surface.
- `agent_workflow/orchestrator.py`: shared orchestration base.
- `agent_workflow/modes/`: public mode surfaces such as `swarm`.
- `agent_workflow/communication/blackboard.py`: canonical shared blackboard.
- `agent_workflow/swarm/`: swarm runtime and compatibility shims.
- `agent_workflow/instrumentation/`: certified time, snapshots, traces, and
  run evidence capture.

Use this package when changing live agent workflows, the CLI, blackboard
coordination, or reproducibility/runtime checks.

## `vao/`

Verified-agent-orchestration compatibility components used by the AutoResearch
benchmark and SWE-bench scaffolds.

Important entrypoints:

- `vao/schemas.py`: shared typed records.
- `vao/orchestrator.py`: compatibility orchestrator logic.
- `vao/structured_edits.py`: edit representation and patch handling.
- `vao/success_metrics.py`: success and first-hit metrics.
- `vao/workspaces.py`: workspace utilities.

Use this package when changing generic verified-run accounting or shared
orchestration abstractions.

## Root-Level Modules

Root-level `src/*.py` modules are the HumanEval+, MBPP+, BBH, and
strategy-routing pipeline inherited from the model-routing track.

Common flows:

- `load_traces.py`: inspect tracked worker/router logs.
- `estimate.py`, `plot.py`: frontier estimation and plotting.
- `estimate_router.py`, `plot_router.py`: retry-router estimation and plotting.
- `run_strategy_eval.py`, `run_strategy_router.py`: strategy-grid execution.
- `analyze_strategy_*.py`, `plot_strategy_results.py`: strategy-result
  analysis.

Use these modules for non-AutoResearch code-benchmark experiments. Their
configs and data live under the matching `experiments/*/` bundle.

## Validation

Safe checks:

```bash
python -m compileall -q src
uv run pytest tests -q
```

Do not launch live model or cluster jobs from this directory unless the user
explicitly requests that run.
