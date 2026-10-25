# Paper Revision

Read `docs/decision-protocol.md`, the experiment README, and the paper evidence
map before editing claims. Existing manuscripts describe prior experiments;
new continuation-policy claims need their own verified evidence.

| Source | Role |
| --- | --- |
| [main.tex](paper/neurips-submission/main.tex) | Compact existing manuscript |
| [arxiv.tex](paper/neurips-submission/arxiv.tex) | Longer AutoResearch manuscript |
| [theory anchor](paper/neurips-submission/archive/theory_anchor.tex) | Consolidated theory under its assumptions |

Use the [theory audit](audits/theory-consolidation.md) to understand historical
claims that were not promoted. Removed drafts, planning documents, and reference
PDFs are recoverable through the [provenance history](history-merge.md), not
current source dependencies.

For every change:

1. Identify the source and specific claim.
2. Link it to a retained experiment and its declared data/protocol limitations.
3. Distinguish observable first-hit outcomes from theoretical quantities.
4. Keep held-out evaluation separate from controller tuning and visible feedback.
5. Update the evidence map, regenerate indexes, and run `make check`.
6. Use `make paper-build` for out-of-tree compilation after paper asset changes.

Referenced figures are vendored under the paper directory. Keep generation code
and evidence canonical in the experiment bundle. Do not claim new counterfactual
continuation outcomes from historical static-model traces.
