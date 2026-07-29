# Knowledge Map

This map is the agent-facing index for the repository. It answers: where is the
paper, where is the evidence, which files are canonical, and which files are
only provenance.

## Core Story

The project studies deployment-aware model and agent-workflow selection. The
paper should connect:

1. A theory of task-conditional model choice, routing information, costs, and
   first-passage or certified proper time.
2. Empirical evidence that model/workflow choice depends on task family,
   resource constraints, and routing information.
3. Reproducible experiment bundles that let a reviewer inspect or regenerate
   key figures without rerunning live agents.

## Paper Sources

| Source | Role |
| --- | --- |
| `paper/neurips-submission/main.tex` | Current compact submission anchor. |
| `paper/neurips-submission/arxiv.tex` | Longer AutoResearch manuscript anchor. |
| `paper/neurips-submission/archive/theory_anchor.tex` | Maximal validated theory anchor. |
| `paper/neurips-submission/archive/Beneventano_Poggio.tex` | Mechanical extraction used as historical/theory context. |
| `paper/neurips-submission/archive/next_steps.tex` | Independent planning document; keep separate. |
| `docs/audits/theory-consolidation.md` | Theorem genealogy, validation notes, and source disposition. |
| `docs/audits/paper-archive-manifest.md` | File-level policy for archived drafts, local snapshots, PDFs, and nearest text neighbors. |

Do not treat `archive/*_local.tex`, old `main_*` drafts, or retained PDFs as
active manuscript sources unless the task explicitly asks for archival review.

## Empirical Evidence

| Question | Canonical bundle |
| --- | --- |
| Which CIFAR-10 starting model is fair for agents? | `experiments/autoresearch-cifar10/starting-model-calibration/` |
| Does the evaluation protocol confound wall time and quality? | `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/` |
| Does shared memory stabilize agent search? | `experiments/autoresearch-cifar10/shared-memory-ablation/` |
| How do independent agents compare with blackboard swarm coordination? | `experiments/autoresearch-cifar10/swarm-vs-independent-agents/` |
| Which worker/model should be routed to which AutoResearch workload? | `experiments/autoresearch-cifar10/three-worker-model-routing/` |
| What is the model-size frontier on HumanEval+? | `experiments/humaneval-plus/qwen-model-size-frontier/` |
| How much does retry allocation help HumanEval+? | `experiments/humaneval-plus/retry-allocation-router/` |
| Does difficulty-conditioned strategy routing help? | `experiments/humaneval-plus/strategy-by-difficulty-grid/` |
| Can an LLM choose useful router context? | `experiments/humaneval-plus/llm-router-context-search/` |
| What model-size evidence exists for MBPP+ and BBH? | `experiments/mbpp-plus/`, `experiments/bbh/` |
| What SWE-bench orchestration scaffolds exist? | `experiments/swebench-verified/` |

`experiments/README.md` is the status table for all bundles.
`docs/audits/experiment-manifest.md` is the generated asset-level audit: use it
to distinguish paper-supporting evidence, partial evidence, scaffolds, and
historical archives before citing or rerunning a bundle.

## Code Surfaces

| Surface | Canonical files |
| --- | --- |
| CLI/runtime | `src/agent_workflow/cli.py`, `src/agent_workflow/modes/`, `src/agent_workflow/orchestrator.py` |
| Blackboard memory | `src/agent_workflow/communication/blackboard.py` |
| Swarm compatibility | `src/agent_workflow/swarm/` |
| AutoResearch benchmark | `autoresearch/benchmark/cifar10/`, `autoresearch/configs/`, `autoresearch/prompts/` |
| AutoResearch analysis | `autoresearch/analysis/`, `autoresearch/scripts/` |
| HumanEval+/MBPP+/BBH pipeline | root-level modules under `src/*.py` plus experiment-local configs |
| SWE-bench runtime | `experiments/swebench-verified/shared-runtime/` |

Compatibility files may keep historical import paths alive, but active behavior
should be implemented once and documented at the canonical surface.
Local maps for implementation work live in `src/README.md`, `scripts/README.md`,
and `autoresearch/scripts/README.md`.

## Reproducibility Surface

| Need | Start here |
| --- | --- |
| Install and smoke-test the repo | `docs/reproducibility.md` |
| Run an offline demo | `docs/demo.md` |
| Edit the paper using repository evidence | `docs/paper-revision-playbook.md` |
| Audit theorem provenance | `docs/audits/theory-consolidation.md` |
| Classify archived paper drafts and snapshots | `docs/audits/paper-archive-manifest.md` |
| Map paper claims to theory and evidence | `docs/paper-evidence-map.md` |
| Inspect experiment bundle assets and reproducibility class | `docs/audits/experiment-manifest.md` |
| Audit manuscript/result mismatch | `docs/audits/manuscript-reproducibility.md` |
| Inspect paper/formal-object/experiment/script index | `docs/audits/knowledge-index.md` |
| Inspect current file inventory | `docs/audits/repo-inventory.md` |
| Inspect command safety and prerequisites | `docs/audits/command-manifest.md` |
| Check requirement-to-evidence handoff status | `docs/audits/agent-readiness-completion-audit.md` |
| Read historical implementation contracts | `docs/specs/README.md` |
| Run the full local agent-readiness gate | `make check` |
| Regenerate the knowledge index | `scripts/build_knowledge_index.py` |
| Regenerate the inventory | `scripts/build_repo_inventory.py` |
| Regenerate the paper archive manifest | `scripts/build_paper_archive_manifest.py` |
| Regenerate the experiment manifest | `scripts/build_experiment_manifest.py` |
| Regenerate the command manifest | `scripts/build_command_manifest.py` |
| Validate agent-facing structure | `scripts/validate_agent_readiness.py` |

## Archive Policy

- `paper/neurips-submission/archive/` contains historical manuscripts and
  references. It is readable context, not active source. Use
  `docs/audits/paper-archive-manifest.md` before mining or deleting anything
  in that directory.
- `experiments/archive/` contains historical benchmark implementations outside
  active evidence.
- `artifacts/source-snapshots/` preserves source-state provenance and should not
  be imported as active code.
- `paper/neurips-submission/figures/` intentionally vendors paper-ready copies
  of figures. The generating experiment remains canonical.

## Before Making Paper Changes

1. Read `docs/paper-revision-playbook.md`.
2. Decide whether the change belongs in `main.tex`, `arxiv.tex`, or
   `archive/theory_anchor.tex`.
3. Check `docs/audits/theory-consolidation.md` for related theorem variants and
   unsupported claims.
4. Check the relevant experiment README for empirical support.
5. Run the smallest relevant validation command from `docs/reproducibility.md`.
6. Update this map or the nearest README if the knowledge structure changes.
