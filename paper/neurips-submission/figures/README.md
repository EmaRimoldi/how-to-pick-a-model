# Paper Figures

This directory contains paper-ready figure copies used by the LaTeX sources in
`paper/neurips-submission/`. They are intentionally vendored here so the paper
can compile from a checkout without reaching into experiment result trees.

Canonical generation code and processed evidence live outside `paper/`, usually
under `autoresearch/scripts/`, `src/`, and the corresponding
`experiments/*/results/` bundle. When a figure is regenerated, update the
experiment output first and then copy the paper-facing artifact here.

Do not treat a copied paper figure as an independent source of evidence. The
experiment README, accounting table, and generation command remain canonical.
