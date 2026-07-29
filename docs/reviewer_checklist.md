# Reviewer Checklist

This checklist is for a technical reviewer who has only a few minutes and wants
to know whether AutoResearch Orchestration is real, inspectable, and honest about its limits.

## Product Clarity

| Question | Where to verify | Status |
|---|---|---|
| What is this? | `README.md` | Benchmark harness for comparing AI-agent workflow modes on one controlled ML task. |
| What concrete task does it run? | `autoresearch/README.md`, `autoresearch/train.py` | Agents optimize CIFAR-10 validation loss by editing one training script. |
| What is the user-facing surface? | `src/agent_workflow/cli.py`, `README.md` | One CLI: `agent-workflow`. |
| What should a reviewer read first? | `docs/demo.md` | Short demo path and evidence path are explicit. |
| Can this be tried without Claude Code or GPU? | `uv run agent-workflow demo` | Offline fixture bundle with `report.html` and Workflow Card. |

## Built System

| Capability | Where to verify | Status |
|---|---|---|
| Single-agent and parallel modes | `src/agent_workflow/modes/`, `src/agent_workflow/launcher.py` | Implemented. |
| Shared memory / blackboard | `src/agent_workflow/communication/`, `src/agent_workflow/swarm/` | Implemented and tested. |
| Claude Code runner | `src/agent_workflow/agents/claude_agent_runner.py` | Implemented; requires local Claude Code auth for live runs. |
| Certified hitting-time analysis | `src/agent_workflow/instrumentation/certified_time.py` | Implemented and tested. |
| Diversity metrics | `src/agent_workflow/analysis/diversity.py` | Implemented and tested. |
| Snapshot and reasoning traces | `src/agent_workflow/instrumentation/` | Implemented and tested. |
| Baseline calibration | `src/agent_workflow/baseline_calibration.py` | Implemented and tested. |
| Offline demo bundle | `src/agent_workflow/demo.py` | Implemented and tested. |
| Public license | `LICENSE`, `pyproject.toml` | MIT license published. |

## Evidence

| Claim | Evidence | Status |
|---|---|---|
| The benchmark starting model was calibrated before agent claims. | `experiments/autoresearch-cifar10/starting-model-calibration/README.md` | 161 controlled evaluations; 1170-update runs are the decision evidence. |
| Evaluation protocol confounds are documented. | `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/README.md` | Fixed-step determinism and fixed-time compute contention are both covered. |
| Shared memory can reduce destructive exploration in this substrate. | `experiments/autoresearch-cifar10/shared-memory-ablation/README.md` | `T07` beats `T06` on best and mean `val_bpb`, with `p < 0.001`. |

## Reproducibility

| Check | Command or file | Status |
|---|---|---|
| Install dependencies | `uv sync --dev --frozen` | Documented. |
| Run structural gate and tests | `make check` | Passing locally. |
| Inspect CLI | `uv run agent-workflow --help` | Passing locally. |
| Prepare benchmark data | `docs/reproducibility.md` | Documented. |
| Run live agent experiments | `docs/reproducibility.md` | Requires Claude Code and isolated workspace. |

## Honest Limits

- This is not a general-purpose agent benchmark yet.
- The current empirical result is strongest for one substrate and one trial
  comparison, not every agent workflow.
- Historical live-agent runs are not bit-for-bit reproducible because external
  model services and agent choices can change.
- No hosted product deployment is claimed yet; this is the evaluation engine and
  evidence trail.

## Next Stronger Proof Points

1. Replicate the `T06`/`T07` result across multiple seeds and model families.
2. Run the calibrated `width30_lr_low` benchmark with fixed-step, logged settings.
3. Add two more benchmark substrates beyond AutoResearch/CIFAR-10.
4. Add CI for tests and public-surface smoke checks.
5. Decide whether to keep `agent-workflow` or rename before the public launch.
