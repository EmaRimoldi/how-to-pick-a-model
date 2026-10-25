# Repository layout

```text
src/vao/
  decisions/       # collectors, budgets, frozen policies and isolated verification
  humaneval/       # HumanEval+ workers, traces, retries and routing
  analysis/        # saved-evidence audits, reports and figures
  *.py             # shared schemas, records and workspace primitives
scripts/
  *.py             # public experiment and saved-data entrypoints
  maintenance/     # repository indexes, validation and manuscript builds
  cluster/         # cluster bootstrap and pinned requirements
experiments/       # seven study bundles: protocols, configurations and evidence
paper/             # manuscript sources and their referenced assets
docs/              # research guides, engineering notes and generated maps
tests/
  analysis/        # saved-data audits and reports
  decisions/       # collection, accounting and verification
  humaneval/       # benchmark worker contracts
  repository/      # indexes, links and command interfaces
  unit/            # shared records, estimators and workspaces
```

## Commands and imports

Install with `uv sync --dev --frozen`. Canonical imports are `vao.decisions`,
`vao.humaneval` and `vao.analysis`; all three ship in the wheel.
Use `python -m vao.humaneval.<module>` for maintained HumanEval+ commands.
Published `python -m src.<module>` commands remain compatible from a checkout.

Published saved-data commands such as `python scripts/verify_feedback_evidence.py`
keep their paths and delegate to `vao.analysis`. New analysis logic belongs in
the package, not in a second script implementation. Repository maintenance is
available through `make indexes`, `make check` and `make paper-build`.

## Provenance boundaries

Study results, configurations, checksums and frozen sources retain their paths
and contents. Source filenames inside historical manifests identify the code
used at collection time; they are not requests to resolve today's module layout.
Historical reports therefore keep their original command/path records. Audits
continue to validate the inert source snapshots and recorded evidence.

Collectors retain their source-drift guards. Moving analysis code does not
permit resuming a completed campaign or bypassing a frozen protocol.
See [reproducibility](../reproducibility.md) for offline commands and requirements.
