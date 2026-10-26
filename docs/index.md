# Documentation

The new [Python repair environment](../experiments/python-repair/checkpoint-environment/README.md)
provides an executable offline demo, immutable checkpoints, matched recovery
requests and task qualification. Its [twelve adapted real-bug tasks](../experiments/python-repair/checkpoint-environment/development/README.md)
and handwritten demo are engineering checks, not model findings; there is no live collector.

| Guide | Purpose |
| --- | --- |
| [Decision protocol](decision-protocol.md) | Research question, actions, costs, first experiment, and implementation limits |
| [Knowledge map](knowledge-map.md) | Retained evidence and code surfaces |
| [Reproducibility](reproducibility.md) | Safe setup, reproduction, and live-run requirements |
| [Review checklist](reviewer_checklist.md) | Evidence and evaluation checks |
| [Manuscript sources](paper/README.md) | Existing manuscripts, theory anchor and empirical recovery draft |
| [Paper evidence](paper-evidence-map.md) | Existing claims and retained baseline evidence |
| [Paper revision](paper-revision-playbook.md) | Source selection and claim discipline |
| [Theory audit](audits/theory-consolidation.md) | Historical theory consolidation and caveats |
| [Manuscript audit](audits/manuscript-reproducibility.md) | Historical accounting and PDF issues |
| [Engineering](engineering/README.md) | Runtime, collector and evidence architecture |
| [Development](engineering/development.md) | Repository checks, reading order and evidence constraints |
| [Context value](../experiments/humaneval-plus/context-value/README.md) | Matched code/feedback conditions and prospective forecasts after failure |
| [Frozen recovery protocol](../experiments/humaneval-plus/context-value/VALIDATION.md) | Development-trained selectors, task holdout, transfer amendment and accounting |
| [Recovery related work](recovery-related-work.md) | Closest precedents and boundaries for a new paper claim |
| [Recovery blog draft](blog/when-to-keep-failed-code.md) | Audited results, static controls, forecast limitations and reproduction |
| [Feedback-only escalation note](blog/feedback-only-escalation.md) | Complete 157-task fixed-policy test, negative primary result, admission/verifier diagnostics and reproduction |
| [Experiment cleanup](audits/experiment-cleanup.md) | Seven maintained bundles, archival decisions and moved paths |
| [Branch review](audits/branch-consolidation.md) | Per-branch decisions, preserved history and consolidation checks |
| [History](history-merge.md) | Source provenance and recoverable cleanup snapshots |

Generated navigation maps: [inventory](audits/repo-inventory.md),
[knowledge](audits/knowledge-index.md), [experiments](audits/experiment-manifest.md),
and [command safety](audits/command-manifest.md). Regenerate with `uv run python scripts/maintenance/workflow.py indexes`.
