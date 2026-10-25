# AutoResearch Orchestration Architecture

AutoResearch Orchestration exposes one runtime package, `agent_workflow`. The architecture is
split between experiment modes, coordination primitives, instrumentation,
evaluation tooling, and curated experiment evidence.

## Canonical Runtime Shape

```text
agent-workflow CLI
  -> modes.parallel       -> agent_workflow.launcher.main_parallel
  -> parallel-shared      -> agent_workflow.launcher.main_parallel_shared
  -> modes.single_long    -> agent_workflow.launcher.main_single_long
  -> single-memory        -> agent_workflow.launcher.main_single_memory
  -> modes.merge          -> agent_workflow.merger.MergeOrchestrator
  -> modes.swarm          -> blackboard surface and swarm runtime
  -> certified-time       -> agent_workflow.instrumentation.certified_time
  -> baseline-calibration -> agent_workflow.baseline_calibration

agent_workflow.communication
  -> SharedMemory blackboard
  -> coordinator helpers

agent_workflow.analysis
  -> H_prior / H_post diversity metrics

agent_workflow.instrumentation
  -> snapshotting
  -> reasoning traces
  -> certified time
```

## Configuration

There is one canonical config surface:

```python
from agent_workflow.config import AgentConfig, ExperimentConfig
```

`AgentConfig` and `ExperimentConfig` live directly in `agent_workflow.config`.

## Orchestration

There is one canonical orchestrator surface:

```python
from agent_workflow.orchestrator import Orchestrator
```

The orchestrator owns process spawning, git worktree isolation, worker
integration, output collection, and report generation.

## Modes

| Mode | Module | Current integration status |
|---|---|---|
| `parallel` | `agent_workflow.modes.parallel` | Independent agents running concurrently |
| `parallel-shared` | `agent_workflow.launcher.main_parallel_shared` | Parallel agents with shared-memory coordination |
| `single_long` | `agent_workflow.modes.single_long` | Single-agent long-budget baseline |
| `single-memory` | `agent_workflow.launcher.main_single_memory` | Single-agent baseline with external memory |
| `merge` | `agent_workflow.modes.merge` | Post-hoc merge over candidate outputs |
| `swarm` | `agent_workflow.modes.swarm` | Shared-blackboard swarm runtime |

## Integrated Components

### Blackboard Communication

`src/agent_workflow/communication/blackboard.py` provides:

- append-only JSONL shared memory
- file locking via `fcntl`
- claim/dedup/release flow
- best-result sidecar
- context filtering for "other agents" reads

### Swarm Coordinator

`src/agent_workflow/communication/coordinator.py` imports the canonical
blackboard module and exposes local coordination helpers for shared-memory
agent workflows.

### Diversity Metrics

`src/agent_workflow/analysis/diversity.py` consolidates H_prior/H_post-style
analysis. Lightweight trajectory DTW is dependency-free; embedding and
weight-space metrics import heavy ML dependencies lazily.

### Instrumentation

`src/agent_workflow/instrumentation/` consolidates:

- snapshotting
- reasoning traces
- certified-time analysis

## Output And Reporting

The reporting pipeline lives under `src/agent_workflow/outputs/` plus mode-level
collector and reporter calls. Merge and swarm workflows write through the same
summary schema where possible.
