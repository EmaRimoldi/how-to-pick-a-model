# Repository history merge

The unified repository has three history roots:

- `theory-of-agents`, the destination history;
- `agentops-lab-public` / `agent-workflow`, imported at commit `9c52da1`;
- the Overleaf manuscript history, imported at commit `dc06c80`.

The merge commit keeps all three as ancestors. Working-tree paths were then
normalized as follows:

| Former path | Unified path |
| --- | --- |
| `agentops-lab-public/experiments/01_*` through `05_*` | `experiments/autoresearch/` |
| `agentops-lab-public/experiments/06_swebench_experimental_scaffold` | `experiments/other/swebench-experimental-scaffold/` |
| `theory-of-agents/experiment_runs` | `experiments/other/strategy-routing-runs/` |
| nested Overleaf checkout `fluid-theory-notes` | `paper/neurips-submission/` |
| older Overleaf checkout `report` | `paper/legacy-report/` |

The historical `agent-workflow` CLI and Python module names remain unchanged to
avoid breaking scripts. The distributable project and repository identity are
`how-to-pick-a-model`.

Original top-level READMEs are retained in `docs/archive/`.
