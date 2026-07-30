# Paper Revision Playbook

This is the operating procedure for an LLM agent preparing the next manuscript
revision. It turns the repository maps into an editing workflow.

## Default Objective

Advance the compact submission around one defensible claim:

> Model and workflow choice should be evaluated as deployment-time
> first-passage performance under task-family, signal, cost, and routing
> constraints, not as a single benchmark score.

Use [`paper-evidence-map.md`](paper-evidence-map.md) for the claim-to-evidence
table and [`audits/theory-consolidation.md`](audits/theory-consolidation.md)
for theorem genealogy.

## Source Routing

| Need | Source |
| --- | --- |
| Active manuscript edits | [`../paper/neurips-submission/arxiv.tex`](../paper/neurips-submission/arxiv.tex) |
| Validated theorem source | [`../paper/neurips-submission/archive/theory_anchor.tex`](../paper/neurips-submission/archive/theory_anchor.tex) |
| Archived draft policy | [`audits/paper-archive-manifest.md`](audits/paper-archive-manifest.md) |

Do not edit archive files as active manuscript source unless the user explicitly
asks for archival consolidation.

## Manuscript Assembly Order

1. Start from [`../paper/neurips-submission/arxiv.tex`](../paper/neurips-submission/arxiv.tex).
2. Keep the introduction aligned with the narrow first-passage/deployment-time
   claim above.
3. Promote only the theory needed by the claim spine:
   `def:certified-time`, `thm:ri-identity`, `thm:four-term`,
   `thm:retry-crossover`, `prop:borrowed-allocation`,
   `prop:approximation-guarantee`, and `def:first-hit-diagnostics`.
4. Use Tier 1 evidence as main paper support.
5. Use Tier 2 evidence only for diagnostics, context, or appendix.
6. Treat Tier 3 evidence as future work or scaffold unless a complete result
   bundle is added.
7. After every paper-facing edit, run `make check`; when TeX Live is available,
   also run `make paper-build`.

## Evidence Discipline

Main evidence should come from:

- [`../experiments/humaneval-plus/strategy-by-difficulty-grid/`](../experiments/humaneval-plus/strategy-by-difficulty-grid/)
- [`../experiments/humaneval-plus/llm-router-context-search/`](../experiments/humaneval-plus/llm-router-context-search/)
- [`../experiments/humaneval-plus/retry-allocation-router/`](../experiments/humaneval-plus/retry-allocation-router/)
- [`../experiments/autoresearch-cifar10/three-worker-model-routing/`](../experiments/autoresearch-cifar10/three-worker-model-routing/)
- [`../experiments/autoresearch-cifar10/shared-memory-ablation/`](../experiments/autoresearch-cifar10/shared-memory-ablation/)
- [`../experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/`](../experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/)

Before citing an experiment, read its `README.md` and prefer accounting tables
or raw/processed result files over paper-ready copied figures.

## Figure Policy

Paper figures live under
[`../paper/neurips-submission/figures/`](../paper/neurips-submission/figures/)
only as vendored compile assets. The experiment bundle and generation command
remain the canonical provenance.

Regenerate the main AutoResearch figure subset with:

```bash
make paper-figures-autoresearch
```

## Validation

Use the one-command local gate:

```bash
make check
```

This regenerates the inventory, knowledge index, paper archive manifest,
experiment manifest, and command manifest; validates agent-facing structure;
byte-compiles `scripts`, `src`, and `autoresearch`; and runs tests.

For manuscript-source edits, add a TeX smoke build when available:

```bash
make paper-build
```

## Failure Modes To Avoid

- Do not claim all experiments are complete.
- Do not cite Tier 3 scaffold evidence as empirical support.
- Do not claim exact packedness without residual diagnostics.
- Do not describe memory or multi-agent coordination as universally beneficial.
- Do not treat archive PDFs or old LaTeX drafts as active paper source.
- Do not cite copied figures as independent evidence.
