.PHONY: indexes readiness compile test check paper-build

UV ?= uv
PYTHON ?= $(UV) run python
PAPER_BUILD_OUT ?= /tmp/how_to_pick_a_model_paper_build

indexes:
	$(PYTHON) scripts/maintenance/build_repo_inventory.py --output docs/audits/repo-inventory.md
	$(PYTHON) scripts/maintenance/build_knowledge_index.py --output docs/audits/knowledge-index.md
	$(PYTHON) scripts/maintenance/build_experiment_manifest.py --output docs/audits/experiment-manifest.md
	$(PYTHON) scripts/maintenance/build_command_manifest.py --output docs/audits/command-manifest.md

readiness:
	$(PYTHON) scripts/maintenance/validate_agent_readiness.py

compile:
	$(PYTHON) -m compileall -q scripts src

test:
	$(UV) run pytest tests -q

check: indexes readiness compile test

paper-build:
	$(PYTHON) scripts/maintenance/check_paper_build.py --output-root $(PAPER_BUILD_OUT)
