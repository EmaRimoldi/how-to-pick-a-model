# Source Code Map

## Python repair environment: `vao/repair/`

- `environment.py`: immutable artifacts, linked checkpoints, matched solver
  requests and offline integrity audits.
- `verifier.py`, `worker.py`: isolated JSON function calls; expectations remain
  in the parent, with separate public and evaluator channels.
- `cli.py`: plan, handwritten demo, task qualification and saved-run audit.

This is engineering infrastructure with no provider transport or model evidence.
See the [environment guide](../experiments/python-repair/checkpoint-environment/README.md).

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

## HumanEval+: `vao/humaneval/`

- `dataset.py`, `models.py`, `execute.py`, `run_eval.py`: worker generation and
  verification on HumanEval+.
- `load_traces.py`, `simulate.py`, `router.py`: recorded attempts and retry routing.
- `estimate*.py`, `plot*.py`, `analyze_strategy*.py`: accounting and figure analysis.
- `run_strategy*.py`, `run_router*.py`: launchers requiring explicit live-run
  authorization and the configured local models or router backend.

CIFAR-10 and its dedicated CLI, adapters and edit/verify harness are retired.
Their complete sources remain in [provenance](../docs/history-merge.md).
Use [reproducibility](../docs/reproducibility.md) for safe commands and dependencies.

## Saved-evidence analysis: `vao/analysis/`

`analyze_*.py` audits recorded banks and reproduces comparisons;
`report_feedback_routing.py` builds the published report and figures;
`verify_feedback_evidence.py` checks the complete frozen BigCodeBench evidence.
The public commands in `scripts/` delegate to these implementations.

Use `python -m vao.humaneval.<module>` or `python -m vao.analysis.<module>`
after installation. The former `python -m src.<module>` HumanEval+ commands
remain available from a source checkout for published workflows. See the
[layout guide](../docs/engineering/layout.md) for placement and compatibility.
