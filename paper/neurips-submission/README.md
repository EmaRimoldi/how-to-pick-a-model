# NeurIPS Submission Sources

This directory is the in-repo Overleaf-compatible paper tree. It should remain
inside the main repository so manuscript text, figures, code, and experiment
evidence stay co-located.

## Active Sources

| File | Role |
| --- | --- |
| `main.tex` | Current compact submission anchor. |
| `arxiv.tex` | Longer AutoResearch manuscript anchor. |
| `references.bib` | Active bibliography. |
| `piers_macro.tex` | Macro file used by the manuscript sources. |
| `figures/` | Paper-ready figure copies used for compilation. |

Build from the repository root when TeX Live is available:

```bash
make paper-build
```

The build script compiles `main.tex` and `arxiv.tex` into `/tmp/...` output
directories, so the Overleaf-compatible source tree stays clean.

## Archive

`archive/` contains consolidated theory, planning notes, extracted references,
and reference PDFs. The important anchors are:

| File | Role |
| --- | --- |
| `archive/theory_anchor.tex` | Maximal validated theory anchor. |
| `archive/Beneventano_Poggio.tex` | Mechanical extraction retained for theory audit context. |
| `archive/next_steps.tex` | Independent planning document; keep separate. |
| `archive/BP.pdf` and `archive/Achille & Soatto.pdf` | External/reference PDFs retained for provenance. |

The generated file-level manifest is
[`../../docs/audits/paper-archive-manifest.md`](../../docs/audits/paper-archive-manifest.md).
It classifies all archived root files and records nearest-neighbor similarity
among archived text sources.

Superseded drafts, local snapshots, and compiled manuscript snapshots were
removed from the current tree after theory consolidation. They remain in
[Git history](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/d98e3f2209c6e470885e748aafb0a41ea6395291/paper/neurips-submission).
The historical submitted PDF has a known text-layer anomaly; use
`make paper-build` to produce PDFs from the active sources. The accounting
discrepancy is documented in
[`../../docs/audits/manuscript-reproducibility.md`](../../docs/audits/manuscript-reproducibility.md).

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
