# Agent Guide

This repository is organized so an LLM agent can continue the paper, inspect the
evidence, and run safe reproducibility checks without first restructuring the
tree.

## Reading Order

1. `README.md`: project scope and top-level directory map.
2. `docs/knowledge-map.md`: semantic map from research questions to files.
3. `docs/reproducibility.md`: commands that can be run safely and what needs
   live model access.
4. `docs/paper-evidence-map.md`: claim-to-theory-to-experiment map for the
   next manuscript revision.
5. `docs/paper-revision-playbook.md`: paper-editing workflow for using the
   theory and evidence maps.
6. `paper/README.md` and `paper/neurips-submission/README.md`: active paper
   sources, archive boundaries, and build instructions.
7. `experiments/README.md`: evidence bundles by benchmark and status.
8. `docs/audits/theory-consolidation.md`: theorem genealogy and source
   disposition.
9. `docs/audits/paper-archive-manifest.md`: generated manifest for archived
   paper drafts, local snapshots, retained PDFs, and deletion-review candidates.
10. `docs/audits/experiment-manifest.md`: generated manifest for experiment
   bundles, reproducibility classes, asset counts, and key files.
11. `docs/audits/command-manifest.md`: generated manifest for Makefile,
   console-script, and script entrypoints with safety classes.
12. `docs/audits/agent-readiness-completion-audit.md`: requirement-to-evidence
   handoff audit for the current repo organization.
13. `docs/audits/knowledge-index.md`: generated retrieval index for paper
   sources, formal objects, experiments, and scripts.
14. `docs/audits/repo-inventory.md`: generated file inventory.

## Canonical Areas

| Area | Use |
| --- | --- |
| `paper/neurips-submission/` | Active manuscript source and paper-ready figures. Keep this inside the repo. |
| `paper/neurips-submission/archive/` | Historical drafts, reference PDFs, and provenance snapshots. Do not edit as active paper source unless explicitly asked. |
| `autoresearch/` | CIFAR-10 AutoResearch benchmark, analysis code, configs, prompts, and figure-generation scripts. |
| `experiments/` | Evidence bundles. Each active bundle should own a `README.md`, configs, data, results, scripts, and figures when available. |
| `src/agent_workflow/` | Agent workflow runtime and CLI compatibility surface. |
| `src/vao/` | Verified-agent-orchestration compatibility/runtime components. |
| `src/README.md`, `scripts/README.md`, `autoresearch/scripts/README.md` | Local code and command maps for implementation work. |
| `docs/` | Human-readable knowledge base, audits, reproducibility instructions, and launch/review material. |
| `docs/specs/` | Historical implementation specs; use bundle READMEs for current status. |
| `artifacts/` | Raw archives and source snapshots retained for provenance, not active source. |

## Safe Defaults

- Prefer read-only inspection before edits.
- Do not launch live model, Claude Code, Slurm, Docker, or provider-backed runs
  unless explicitly requested.
- Use `docs/audits/command-manifest.md` before running an unfamiliar command.
- Treat `paper/neurips-submission/arxiv.tex` as the active manuscript and
  `paper/neurips-submission/archive/theory_anchor.tex` as the validated theory anchor.
- Treat experiment `README.md` files, `docs/audits/experiment-manifest.md`, and
  `docs/reproducibility.md` as the authoritative operational descriptions.
- Keep generated local outputs under ignored paths such as `tmp/`, `runs/`, or
  `/tmp/...`.
- Preserve archive files unless the user explicitly approves deletion.

## Reproducibility Commands

Fast structural checks:

```bash
make check
```

Expanded form:

```bash
python scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md
python scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md
python scripts/build_paper_archive_manifest.py --output docs/audits/paper-archive-manifest.md
python scripts/build_experiment_manifest.py --output docs/audits/experiment-manifest.md
python scripts/build_command_manifest.py --output docs/audits/command-manifest.md
python scripts/validate_agent_readiness.py
python -m compileall -q scripts src autoresearch
uv run pytest tests -q
```

Paper-facing figure regeneration example:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

## Edit Discipline

- Update the closest README when moving, adding, or retiring a bundle.
- If a paper figure is copied into `paper/neurips-submission/figures/`, keep the
  experiment output and command as canonical provenance.
- If a file becomes compatibility-only, make it a small wrapper and point to the
  canonical implementation.
- After cleanup, run `make indexes` so future agents see the current structure.
