# Source Code Map

`vao/decisions/progress_history.py` is the next offline development prototype:
finite-domain tasks, exhaustive bounded-expression verification and paired
continue/restart prompt projections. It contains no provider or training path;
see the [draft design](../experiments/finite-domain/progress-history/README.md).

## Verified execution: `vao/`

`orchestrator.py`, `schemas.py`, `workspaces.py`, `success_metrics.py`, and
`agents/` provide edit/verify execution, observable records, model adapters,
and supported session behavior. These are the starting points for matched
checkpoint continuations. The proposed state-conditioned controller is not yet
implemented. `decisions/` adds budgeted OpenRouter calls and a matched
one-checkpoint HumanEval+ collector with separate visible and evaluation channels.
`decisions/context_value.py` adds code/feedback ablations and prospective zero-shot
API forecasts; `recovery_policy.py` implements the limited one-checkpoint
selector described in that bundle. `transfer*.py` adds the separate MBPP+
replication. `feedback_routing.py` implements the completed BigCodeBench fixed
policies, sharing accounting and verification rather than a learned controller. Use
`docs/decision-protocol.md` before extending the runtime.

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

Historical MBPP/BBH loaders and analyses remain retired. The focused
`decisions/transfer.py` collector extends the retained recovery experiment to
MBPP+, with official input/oracle handling and a frozen cross-benchmark protocol.
See [the architecture](../docs/engineering/architecture.md) for package boundaries
and frozen-source provenance. Safe checks: `make check`. Do not start live model or cluster work during an audit.
