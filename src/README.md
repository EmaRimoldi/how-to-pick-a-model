# Source Code Map

## Verified execution: `vao/`

`orchestrator.py`, `schemas.py`, `workspaces.py`, `success_metrics.py`, and
`agents/` provide edit/verify execution, observable records, model adapters,
and supported session behavior. These are the starting points for matched
checkpoint continuations. The proposed state-conditioned controller is not yet
implemented. `decisions/` adds budgeted OpenRouter calls and a matched
one-checkpoint HumanEval+ collector with separate visible and evaluation channels; use `docs/decision-protocol.md` before extending the runtime.

## Baseline CLI: `agent_workflow/`

Existing CLI modes, snapshots, trace/cost instrumentation, and reports remain
available as baseline tools. They are not a claim that a particular agent
architecture is best or that dynamic continuation decisions already work.

## HumanEval+: root `src/*.py`

- `dataset.py`, `models.py`, `execute.py`, `run_eval.py`: retained HumanEval+
  worker generation and verification.
- `load_traces.py`, `simulate.py`, `router.py`: recorded attempts and retry routing.
- `estimate*.py`, `plot*.py`, `analyze_strategy*.py`: baseline accounting and plots.
- `run_strategy*.py`, `run_router*.py`: experiment launch surfaces; inspect their
  configs and model-access requirements before live use.

MBPP/BBH-specific loaders and analyses have been retired with their bundles.
Safe checks: `make check`. Do not start live model or cluster work during an audit.
