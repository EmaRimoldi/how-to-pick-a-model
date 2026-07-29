# Root Scripts

Root-level scripts are repository utilities and legacy launch helpers. Prefer
package modules for reusable behavior; use these scripts as command entrypoints.

## Repository Indexes

- `build_repo_inventory.py`: deterministic file inventory for agents and
  reviewers.
- `build_knowledge_index.py`: compact retrieval index for paper sources,
  formal objects, experiment bundles, and script entrypoints.
- `build_experiment_manifest.py`: generated asset manifest for experiment
  bundles, reproducibility classes, result/config/script counts, and key files.
- `build_command_manifest.py`: generated safety manifest for Makefile targets,
  console scripts, and repository script entrypoints.
- `build_paper_archive_manifest.py`: generated policy manifest for root-level
  archived paper drafts, local snapshots, retained PDFs, and nearest text
  neighbors.
- `validate_agent_readiness.py`: one-command structural gate for generated
  indexes, canonical docs, paper-evidence references, local-path hygiene, links,
  and documented duplicates.
- `check_paper_build.py`: out-of-tree `pdflatex`/`bibtex` smoke build for the
  active manuscript sources.
- `agent_index_config.py`: shared configuration used by the index and readiness
  scripts; it is support code, not a command entrypoint.

Regenerate generated audits after structural cleanup:

```bash
make indexes
python scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md
python scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md
python scripts/build_paper_archive_manifest.py --output docs/audits/paper-archive-manifest.md
python scripts/build_experiment_manifest.py --output docs/audits/experiment-manifest.md
python scripts/build_command_manifest.py --output docs/audits/command-manifest.md
python scripts/validate_agent_readiness.py
```

Use `make check` for the full local agent-readiness gate: regenerated indexes,
readiness validation, bytecode compilation, and the test suite.

Use `make paper-build` after paper-source edits when TeX Live is available.

## Product And Evidence Figures

- `plot_experiment_overview.py`
- `plot_product_evidence_assets.py`
- `plot_autoresearch_readme_figures.py`
- `plot_autoresearch_neural_substrates.py`

These read checked-in evidence and produce review/README-facing assets.

## Legacy Agent-Workflow Launch Helpers

- `run_single_long_experiment.py`
- `run_parallel_experiment.py`
- `run_merge_phase.py`
- `run_best_params_merge.py`
- `analyze_runs.py`
- `compare_experiments.py`
- `benchmark_parallel_capacity.py`

These may invoke live workflows or inspect generated `runs/` directories. Check
`docs/reproducibility.md` and run `uv run agent-workflow doctor` before using
them for live experiments.

## Cluster Bootstrap

- `bootstrap_engaging.sh`: cluster environment bootstrap for the
  HumanEval+/MBPP+/BBH routing stack.

Do not run cluster or provider-backed scripts during a read-only audit.
