.PHONY: indexes readiness compile test check paper-build paper-figures-autoresearch

PYTHON ?= python
UV ?= uv
PAPER_BUILD_OUT ?= /tmp/how_to_pick_a_model_paper_build
AUTORESEARCH_FIGURE_OUT ?= /tmp/how_to_pick_a_model_autoresearch

indexes:
	$(PYTHON) scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md
	$(PYTHON) scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md
	$(PYTHON) scripts/build_paper_archive_manifest.py --output docs/audits/paper-archive-manifest.md
	$(PYTHON) scripts/build_experiment_manifest.py --output docs/audits/experiment-manifest.md
	$(PYTHON) scripts/build_command_manifest.py --output docs/audits/command-manifest.md

readiness:
	$(PYTHON) scripts/validate_agent_readiness.py

compile:
	$(PYTHON) -m compileall -q scripts src autoresearch

test:
	$(UV) run pytest tests -q

check: indexes readiness compile test

paper-build:
	$(PYTHON) scripts/check_paper_build.py --output-root $(PAPER_BUILD_OUT)

paper-figures-autoresearch:
	$(UV) run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
	  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
	  --out-dir $(AUTORESEARCH_FIGURE_OUT)
