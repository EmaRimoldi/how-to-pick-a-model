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
| `agentops-lab-public/experiments/01_*` through `05_*` | five question-named bundles under `experiments/autoresearch-cifar10/` |
| `agentops-lab-public/experiments/06_swebench_experimental_scaffold` | deduplicated into `experiments/swebench-verified/neutral-100-meta-design-scaffold/` and `shared-runtime/` |
| `theory-of-agents/experiment_runs` | `experiments/humaneval-plus/strategy-by-difficulty-grid/` and `llm-router-context-search/` |
| nested Overleaf checkout `fluid-theory-notes` | `paper/neurips-submission/` |
| `NeurIPS_2026/Archive/stateful_query_engine` | `experiments/archive/stateful-query-engine/`, labelled as a historical implementation with no result, report, or run artifacts |
| `NeurIPS_2026/step1` | `experiments/humaneval-plus/verifier-guided-dag-induction-smoke/` |
| `NeurIPS_2026/swebench` | four named bundles under `experiments/swebench-verified/` |
| unique `NeurIPS_2026/autoresearch` support code | root `autoresearch/` package |
| unique historical AutoResearch figures | `experiments/autoresearch-cifar10/three-worker-model-routing/results/figures/archive/distribution-aware-orchestration/` |

The historical `agent-workflow` CLI and Python module names remain unchanged to
avoid breaking scripts. The distributable project and repository identity are
`how-to-pick-a-model`.

Original top-level READMEs and diagnostics are retained in `docs/archive/`.

## Working-tree cleanup

The October 2026 cleanup retired material that is not used by the current
manuscripts, runtime, or evidence bundles. The last complete pre-cleanup tree is
[`d98e3f2`](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/d98e3f2209c6e470885e748aafb0a41ea6395291).
No Git history was rewritten.

- Removed source-state snapshots and platform-specific Python bytecode;
  the three source snapshots differed from canonical copies only in paths.
- Removed pre-determinism backups, disconnected AutoResearch legacy code,
  the unrun stateful-query benchmark, and unused candidate-plot outputs and code.
- Removed the old landing page, launch drafts, and superseded positioning notes.
- Removed superseded manuscript drafts, local copies, their bibliography, and
  compiled manuscript snapshots. Validated theory remains in `theory_anchor.tex`;
  the independent planning document and reference sources remain in the archive.
- The historical submitted PDF has a confirmed text-layer anomaly. It is no
  longer distributed in the current tree; current PDFs must be built from the
  active LaTeX sources. The reproducibility audit records the historical issues.

Raw campaign archives, experiment inputs/results, active manuscripts and their
figure dependencies, and the two runtime packages were preserved.
