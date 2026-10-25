# Repository history and provenance

On 24 October 2026, the maintained branch was consolidated from 440 imported and
incremental commits into six research milestones. This is a retrospective squash
of existing work, not a claim that the experiments followed a preregistered
six-stage plan. The current code, configurations, data, results, source snapshots,
manuscripts and scientific limitations are preserved. Consolidation commits use
the curation date; original dates and attribution remain in the provenance history.

Later maintenance builds on these milestones. The [experiment cleanup](audits/experiment-cleanup.md)
consolidates calibration and archives the initial pilot, memory study and
superseded variants; it preserves the current paper inputs and recorded core results.

## Maintained milestones

| Stage | Scope | Original source snapshot |
| --- | --- | --- |
| 1 | Verified-task runtime, eight AutoResearch/HumanEval+ baseline bundles, manuscripts and reproduction tools | `7c009cc1cf06299596c202c8fd7ed383f0158d04` |
| 2 | Budgeted checkpoint collection, isolated public/private verification and development pilot | `5bc534cc4fc82cac49aa6ffb4b7d913e74b34e22` |
| 3 | Matched failed-artifact/feedback interventions and prospective forecasts | `ca84cc062b3300b96404d77a4e7802f97853732e` |
| 4 | Frozen recovery selectors, declared producer-transfer validation and cost accounting | `cb6caa32d7aad2d3fdfe63ea1d31526f01e9801e` |
| 5 | MBPP+ replication, forecast controls, paper inputs and transport-stop regression fix | `244eb4fe8293c4396a6e05c8df495b5527cb6121` |
| 6 | Complete BigCodeBench fixed-policy study, shared runtime maintenance and current documentation | `66ea3bf14741f2df19e12e9fb88279804ee255b8` |

Stages 1–5 reproduce their source trees exactly. Stage 6 preserves the final
verified implementation and scientific assets while updating history navigation
and the AutoResearch overview. Import merges, duplicate squash ancestry, repeated
manuscript revisions and the retired SAI-3 line are omitted from maintained main's
ancestry. They remain available for provenance rather than as active branches.

Negative findings, exploratory status, missing raw traces, censored outcomes and
interim disclosures have not been removed or reclassified. The limited checkpoint
selector remains distinct from a general continuation controller.

## Retrieve original sources

The annotated tag
[`provenance/pre-curation-2026-10-24`](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/provenance/pre-curation-2026-10-24)
points to the original main at `66ea3bf14741f2df19e12e9fb88279804ee255b8`.
It retains all 440 original commits, including the source SHAs recorded in
collection manifests and the original contributor attribution. This tag is an
archive, not a second maintained release or branch.

Original hashes in frozen records are provenance identifiers; they are not
rewritten to pretend collection used the new commits. A normal saved-data audit
uses the tracked inert source snapshots and requires no historical checkout.
To inspect an original implementation, including from a shallow clone:

```bash
git fetch origin tag provenance/pre-curation-2026-10-24
git show d65fbde:src/vao/decisions/feedback_routing.py
```

Before rewriting main, a full Git bundle was restored into a separate bare
repository and checked with `git fsck --full`. All 18 LFS objects in the original
history were fetched, copied to a separate local backup and SHA-256 verified.
Branch/PR metadata and an old-to-new milestone map were also retained locally.

Existing PR discussions and original commit links describe the historical work.
The [branch review](audits/branch-consolidation.md) records the assessment made
before history curation, including why the divergent theory line was retired.

## Original sources and scope reductions

The original repository unified four histories:

- `theory-of-agents`;
- `agentops-lab-public` / `agent-workflow`, imported at `9c52da1`;
- the Overleaf manuscript history, imported at `dc06c80`;
- `distribution-aware-orchestration`, recovered from `NeurIPS_2026` at `9689508`.

The October scope reductions retired unused source copies and bytecode, obsolete
launch/positioning material, superseded manuscript drafts, unrun scaffolds,
peripheral BBH/SWE-bench/MBPP studies, DAG prototypes and historical swarm
comparisons. The focused later MBPP+ replication is a separate retained study.
Active manuscripts, eight baseline bundles, runtime instrumentation and referenced
raw archives were preserved. The historical submitted PDF's text-layer anomaly
remains documented in the [manuscript audit](audits/manuscript-reproducibility.md).

The archive tag retains these useful recovery points:

| Original snapshot | Historical purpose |
| --- | --- |
| `d98e3f2209c6e470885e748aafb0a41ea6395291` | Complete tree before the first working-tree cleanup |
| `2f2ccefb8b7c9bf34ba398ad499542cf50c03982` | Tree before narrowing to sequential model decisions |
| `5bc534cc4fc82cac49aa6ffb4b7d913e74b34e22` | Last main copy of retired specification/protocol documents |
| `b8f57d74e2dc8b36aff94a53e48ed4ca5921d320` | Retired SAI-3 packed-time benchmark and divergent theory drafts |

Use the archive tag before `git show` with any of these hashes. Current contracts
live in the decision protocol, experiment READMEs and tested code. Do not revive
an archived collector or promote its claims merely because its source is recoverable.
