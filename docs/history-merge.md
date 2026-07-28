# Repository history merge

The unified repository has four history roots:

- `theory-of-agents`, the destination history;
- `agentops-lab-public` / `agent-workflow`, imported at commit `9c52da1`;
- the Overleaf manuscript history, imported at commit `dc06c80`;
- `distribution-aware-orchestration`, recovered from the cluster checkout
  `NeurIPS_2026` at commit `9689508`.

The merge commits keep all four as ancestors. Working-tree paths were then
normalized as follows:

| Former path | Unified path |
| --- | --- |
| `agentops-lab-public/experiments/01_*` through `05_*` | `experiments/autoresearch/` |
| `agentops-lab-public/experiments/06_swebench_experimental_scaffold` | `experiments/other/swebench-experimental-scaffold/` |
| `theory-of-agents/experiment_runs` | `experiments/other/strategy-routing-runs/` |
| nested Overleaf checkout `fluid-theory-notes` | `paper/neurips-submission/` |
| older Overleaf checkout `report` | `paper/legacy-report/` |
| `NeurIPS_2026/Archive` | `experiments/other/distribution-aware-orchestration/Archive/` |
| `NeurIPS_2026/step1` | `experiments/other/distribution-aware-orchestration/step1/` |
| `NeurIPS_2026/swebench` | `experiments/other/distribution-aware-orchestration/swebench/` |
| unique `NeurIPS_2026/autoresearch` support code | root `autoresearch/` package |
| unique historical AutoResearch figures | `experiments/autoresearch/05_autoresearch_model_routing/results/figures/archive/distribution-aware-orchestration/` |

The historical `agent-workflow` CLI and Python module names remain unchanged to
avoid breaking scripts. The distributable project and repository identity are
`how-to-pick-a-model`.

Original top-level READMEs and diagnostics are retained in `docs/archive/`.
