# NeurIPS Submission Sources

This directory is the in-repo Overleaf-compatible paper tree. It should remain
inside the main repository so manuscript text, figures, code, and experiment
evidence stay co-located.

## Active Sources

| File | Role |
| --- | --- |
| `arxiv.tex` | Active AutoResearch manuscript anchor. |
| `references.bib` | Active bibliography. |
| `figures/` | Paper-ready figure copies used for compilation. |

Build from the repository root when TeX Live is available:

```bash
make paper-build
```

The build script compiles `arxiv.tex` into a `/tmp/...` output directory, so
the Overleaf-compatible source tree stays clean.

## Archive

`archive/` contains historical drafts, extracted references, local snapshots,
and retained PDFs. The important anchors are:

| File | Role |
| --- | --- |
| `archive/theory_anchor.tex` | Maximal validated theory anchor. |
| `archive/submitted-manuscript.pdf` | Immutable submitted manuscript snapshot. |
| `archive/BP.pdf` and `archive/Achille & Soatto.pdf` | External/reference PDFs retained for provenance. |

The generated file-level manifest is
[`../../docs/audits/paper-archive-manifest.md`](../../docs/audits/paper-archive-manifest.md).
It classifies all archived root files and records nearest-neighbor similarity
among archived text sources. Removed editable sources remain available in Git
history.

Do not edit archive files as the active paper unless the task explicitly asks
for archival consolidation.

## Figure Policy

Figures are vendored in `figures/` so the paper compiles from this directory.
The experiment directory, accounting tables, and generation scripts remain the
canonical evidence. See `figures/README.md` before adding or replacing figures.

## Theory Policy

Before promoting a theorem or definition into an active manuscript, inspect
`docs/audits/theory-consolidation.md` and the generated
`docs/audits/knowledge-index.md`. The audit identifies which archived claims
were validated, which were only conceptual, and which were not promoted because
their proofs were insufficient; the index points to the current formal objects
by source file and line.

For the end-to-end manuscript-editing procedure, use
`docs/paper-revision-playbook.md`.
