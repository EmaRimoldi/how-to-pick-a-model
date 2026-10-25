# Manuscript Sources

| File | Role |
| --- | --- |
| `main.tex` | Compact existing manuscript |
| `arxiv.tex` | Longer AutoResearch manuscript |
| `archive/theory_anchor.tex` | Consolidated theory under stated assumptions |
| `references.bib`, `piers_macro.tex` | Active bibliography and macros |
| `figures/` | The 19 figure files referenced by the two manuscripts |

```bash
uv run python scripts/maintenance/workflow.py paper-build
```

Run from the repository root with TeX Live installed. PDFs and intermediate
files are written out of tree under `/tmp/`.

The paper is existing research background. See
[decision protocol](../../decision-protocol.md) and
[claim/evidence map](../../paper-evidence-map.md) before adding new
continuation-policy claims. Historical issues remain in the
[manuscript audit](../../audits/manuscript-reproducibility.md).

The archive now retains only the theory anchor. Removed drafts, planning notes,
reference/extracted sources, and compiled snapshots are recoverable through
[repository history](../../history-merge.md). Original theory consolidation
and unsupported claims remain documented in the historical theory audit.

CIFAR-10 experiment code, data and launchers are retired from the maintained
package. Its historical figures remain embedded here; recover their source
material through [provenance](../../history-merge.md). The current experiment
index contains seven coding-task studies.
