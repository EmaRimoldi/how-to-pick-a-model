# Agent Readiness Completion Audit

This audit maps the repository-organization objective to the current evidence
that an LLM agent can continue the paper without first restructuring the repo.

## Objective Requirements

| Requirement | Evidence | Status |
| --- | --- | --- |
| Provide a clear entrypoint for a new LLM. | `AGENTS.md`, `README.md`, `docs/knowledge-map.md` | satisfied |
| Separate active manuscript sources from archive/provenance. | `paper/neurips-submission/README.md`, `docs/audits/paper-archive-manifest.md`, `docs/audits/theory-consolidation.md` | satisfied |
| Preserve paper-development context and next edit path. | `docs/paper-evidence-map.md`, `docs/paper-revision-playbook.md`, `paper/README.md` | satisfied |
| Make experiment evidence discoverable and ranked by usability. | `experiments/README.md`, `docs/audits/experiment-manifest.md`, `docs/reproducibility.md` | satisfied |
| Make command entrypoints safe for agents. | `docs/audits/command-manifest.md`, `scripts/README.md`, `autoresearch/scripts/README.md` | satisfied |
| Make code surfaces navigable. | `src/README.md`, `scripts/README.md`, `autoresearch/scripts/README.md`, `docs/audits/knowledge-index.md` | satisfied |
| Detect stale generated knowledge after structural edits. | `make indexes`, `python scripts/validate_agent_readiness.py`, generated audits under `docs/audits/` | satisfied |
| Detect unexpected exact duplicates in source/document types. | `docs/audits/repo-inventory.md`, `scripts/build_repo_inventory.py`, `scripts/validate_agent_readiness.py` | satisfied |
| Keep copied paper figures tied to experiment provenance. | `paper/neurips-submission/figures/README.md`, `docs/audits/knowledge-index.md`, `docs/paper-evidence-map.md` | satisfied |
| Verify the active paper can compile. | `make paper-build`, `scripts/check_paper_build.py` | satisfied when TeX Live is installed |
| Provide one local gate for agent-readiness. | `make check` | satisfied |

## Current Canonical Handoff

For a new LLM agent, the working sequence is:

1. Read `AGENTS.md`.
2. Read `docs/knowledge-map.md`.
3. Read `docs/paper-revision-playbook.md` for manuscript work.
4. Use `docs/paper-evidence-map.md` to connect claims, theory, and evidence.
5. Use `docs/audits/experiment-manifest.md` before citing experiment results.
6. Use `docs/audits/command-manifest.md` before running unfamiliar commands.
7. Run `make check` after structural, code, documentation, or paper-supporting
   evidence changes.
8. Run `make paper-build` after manuscript-source edits when TeX Live is
   available.

## Verification Gates

The default gate is:

```bash
make check
```

It regenerates:

- `docs/audits/repo-inventory.md`
- `docs/audits/knowledge-index.md`
- `docs/audits/paper-archive-manifest.md`
- `docs/audits/experiment-manifest.md`
- `docs/audits/command-manifest.md`

Then it validates agent-facing structure, byte-compiles `scripts`, `src`, and
`autoresearch`, and runs the test suite.

The paper build gate is:

```bash
make paper-build
```

It compiles `paper/neurips-submission/arxiv.tex` out of tree.

## Residual Risk

- Live model, Slurm, Docker, SWE-bench, and provider-backed runs remain outside
  the default gate by design.
- Some experiment bundles are intentionally partial, historical, or scaffold
  evidence; use `docs/audits/experiment-manifest.md` before citing them.
- Archive TeX files remain for provenance; use
  `docs/audits/paper-archive-manifest.md` before mining or deleting them.
- The full objective stays valid only if generated audits are refreshed after
  structural changes.
