# Repository history and provenance

On 25 October 2026, maintained `main` was consolidated into one curated snapshot
from eight commits. This is a retrospective packaging change, not a claim that
all research was performed in one step or followed a preregistered plan. The
snapshot uses the curation date. Original experiment dates, contributors, source
hashes and scientific limitations remain in the recorded evidence and archives.

## Recover earlier versions

| Provenance tag | Contents |
| --- | --- |
| [`provenance/pre-cleanup-2026-10-25`](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/provenance/pre-cleanup-2026-10-25) | The previous eight-commit main at `a188ddc5390530908f557cddf8b6fab27c95d3c8`, before final data cleanup and snapshot consolidation |
| [`provenance/pre-curation-2026-10-24`](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/provenance/pre-curation-2026-10-24) | All 440 original imported/incremental commits, ending at `66ea3bf14741f2df19e12e9fb88279804ee255b8` |

These are provenance archives, not separately maintained branches. Fetch them
explicitly when using a shallow clone:

```bash
git fetch origin tag provenance/pre-cleanup-2026-10-25
git fetch origin tag provenance/pre-curation-2026-10-24
git show d65fbde:src/vao/decisions/feedback_routing.py
```

Frozen collection hashes identify the original sources. They are not rewritten
to suggest that collection used the new snapshot. Normal saved-data audits use
the tracked inert source snapshots and require no historical checkout.

The original repository unified `theory-of-agents`, `agentops-lab-public` /
`agent-workflow` (imported at `9c52da1`), Overleaf (`dc06c80`) and
`distribution-aware-orchestration` (`9689508`). Original dates and attribution
are retained in the archive; contributor credit is carried into the snapshot.
The intermediate six-milestone curation on 24 October was also retrospective.

## Scope reductions

The [cleanup record](audits/experiment-cleanup.md) describes consolidated
calibration, archived memory/pilot studies, superseded accounting panels,
obsolete tooling and removed scheduler/debug output. Accepted raw observations,
complete negative outcomes, censored states, budgets, frozen sources, protocol
amendments and held-out selection boundaries remain intact. Main-figure pooled
accounting and the balanced sensitivity are documented as distinct panels.

The [branch review](audits/branch-consolidation.md) records the earlier
consolidation, including why the divergent SAI-3 theory line was retired. The
historical submitted PDF's anomaly remains in the
[manuscript audit](audits/manuscript-reproducibility.md). Existing PR discussions
describe the historical work; they do not establish a new experiment.

Useful original recovery points remain in the original-history tag:

| Original snapshot | Purpose |
| --- | --- |
| `d98e3f2209c6e470885e748aafb0a41ea6395291` | Complete tree before the first working-tree cleanup |
| `2f2ccefb8b7c9bf34ba398ad499542cf50c03982` | Tree before narrowing to sequential model decisions |
| `5bc534cc4fc82cac49aa6ffb4b7d913e74b34e22` | Retired specification/protocol documents |
| `b8f57d74e2dc8b36aff94a53e48ed4ca5921d320` | Retired SAI-3 benchmark and divergent drafts |

Before the latest rewrite, the full Git bundle was restored into a separate bare
repository and checked with `git fsck --full`. All 18 historical LFS objects were
copied to a separate local backup and SHA-256 verified. The previous eight-commit
main is preserved by its provenance tag. Current contracts live in the decision
protocol, experiment READMEs and tested code; archived sources are not permission
to resume a completed campaign.
