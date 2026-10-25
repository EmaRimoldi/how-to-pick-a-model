# Source Code Map

## Coding-task collectors: `vao/decisions/`

- `openrouter.py`: provider receipts, conservative admissions and budget journals.
- `verification.py`, `verifier_worker.py`: isolated HumanEval+/MBPP+ verification.
- `pilot.py`, `context_value.py`: checkpoint collection and code/feedback conditions.
- `recovery.py`, `recovery_policy.py`, `recovery_import.py`: frozen one-checkpoint
  selection, producer transfer and saved-data replay.
- `transfer*.py`: MBPP+ replication and prospective forecasts.
- `bigcode.py`, `bigcode_worker.py`, `feedback_routing.py`: completed BigCodeBench
  fixed-policy trajectories, public feedback and evaluator-only labels.

Shared `schemas.py`, `records.py`, `workspaces.py` and related primitives retain
observable-run formats and validation utilities. A general multi-step controller
remains future work; see the [decision protocol](../docs/decision-protocol.md).

## HumanEval+: root `src/*.py`

- `dataset.py`, `models.py`, `execute.py`, `run_eval.py`: worker generation and
  verification on HumanEval+.
- `load_traces.py`, `simulate.py`, `router.py`: recorded attempts and retry routing.
- `estimate*.py`, `plot*.py`, `analyze_strategy*.py`: accounting and figure analysis.
- `run_strategy*.py`, `run_router*.py`: launchers requiring explicit live-run
  authorization and the configured local models or router backend.

CIFAR-10 and its dedicated CLI, adapters and edit/verify harness are retired.
Their complete sources remain in [provenance](../docs/history-merge.md).
Use [reproducibility](../docs/reproducibility.md) for safe commands and dependencies.
