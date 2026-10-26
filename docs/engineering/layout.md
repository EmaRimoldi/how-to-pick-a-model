# Repository layout

```text
.github/           # GitHub workflows and issue/PR templates
docs/
  paper/           # manuscript sources, theory and referenced figures
  engineering/     # architecture, layout and optional environment example
  audits/          # generated maps and historical audits
experiments/       # seven study bundles: protocols, configurations and evidence
scripts/
  *.py             # public experiment and saved-data entrypoints
  maintenance/     # repository indexes, validation and manuscript builds
  cluster/         # cluster bootstrap and pinned requirements
src/vao/
  decisions/       # collectors, budgets, policies and isolated verification
  humaneval/       # HumanEval+ workers, traces, retries and routing
  analysis/        # saved-evidence audits, reports and figures
  *.py             # shared schemas, records and workspace primitives
tests/             # analysis, decisions, humaneval, repository and unit checks
LICENSE            # project license
pyproject.toml     # package and tool configuration
uv.lock            # reproducible Python dependency resolution
.gitignore         # local outputs and credential exclusions
```

## Commands and imports

Install with `uv sync --dev --frozen`. Canonical imports are `vao.decisions`,
`vao.humaneval` and `vao.analysis`; all three ship in the wheel.
Use `python -m vao.humaneval.<module>` for maintained HumanEval+ commands.
Published `python -m src.<module>` commands remain compatible from a checkout.

Published saved-data commands such as `python scripts/verify_feedback_evidence.py`
keep their paths and delegate to `vao.analysis`. New analysis logic belongs in
the package, not in a second script implementation. Repository maintenance is
available through one Python runner:

```bash
uv run python scripts/maintenance/workflow.py check
```

Use `indexes`, `readiness`, `compile`, `test` or `paper-build` instead of `check`
for individual operations. The full check regenerates maps before validating
references, compiling Python and running the offline tests.

## Provenance boundaries

Study results, configurations, checksums and frozen sources retain their paths
and contents. Manuscripts live under `docs/paper/`; their guides and build
commands use this location. Source filenames inside historical manifests identify
the code used at collection time; they are not requests to resolve today's module layout.
Historical reports therefore keep their original command/path records. Audits
continue to validate the inert source snapshots and recorded evidence.

Collectors retain their source-drift guards. Moving analysis code does not
permit resuming a completed campaign or bypassing a frozen protocol.
See [reproducibility](../reproducibility.md) for offline commands and requirements.

## Root directory policy

Keep the five project areas (`docs`, `experiments`, `scripts`, `src`, `tests`)
and standard project/automation files at the root. Manuscripts belong in
`docs/paper`; example environment settings belong beside the engineering guide.
Development instructions live in [development.md](development.md). Repository
checks and paper builds use `scripts/maintenance/workflow.py`; Make is not required.
