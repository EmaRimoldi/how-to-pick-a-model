# Experiment cleanup — 24 October 2026

The maintained experiment index now contains nine bundles instead of twelve.
This cleanup changes scope and organization, not the reported core outcomes.
The full original studies remain under the
[provenance tag](../history-merge.md).

| Former material | Disposition |
| --- | --- |
| AutoResearch starting-model calibration | Merged into `experiments/autoresearch-cifar10/calibration/`, with methods in `starting-model.md` and original results under `results/starting-model/` |
| AutoResearch evaluator/compute calibration | Same bundle, with methods in `evaluation-controls.md` and retained controls under `results/evaluation-controls/` |
| Exploratory shared-memory ablation | Archived outside the maintained tree; limited replication and missing raw live-agent directories prevent a robust comparative claim |
| Initial OpenRouter continuation pilot | Archived as a standalone study; original data/configuration remain as context-value provenance for billing, task exclusions and runtime regression checks |
| Superseded 2×2 pilot analyses and historical figure variants | Removed from the current tree; original versions remain in the archive |

## Preserved evidence and paths

The 161-evaluation starting-model tables and figures are moved unchanged. The
fixed-time CPU table and fixed-step CPU measurements are moved unchanged. The
five-run determinism record is rescued from the superseded directory before
retiring its unrelated memory analyses. Distinct calibration protocols remain
separate within one bundle; their scores are not pooled.

`calibration/scripts/plot_baseline.py` and
`calibration/scripts/plot_evaluation_protocol_calibration.py` resolve their moved
inputs relative to their own files. Both accept `--output-dir` for safe, out-of-tree
figure reproduction.

The pilot's eight data/configuration files are byte-identical copies under
`experiments/humaneval-plus/context-value/provenance/continuation-pilot/`, with a
checksum inventory. They retain the 24 observed development tasks, 88 receipts,
all scored outcomes, the original budget journal and the original configuration.
The shared collector, transport, accounting and verifier code remain in place;
their tests use the relocated frozen configuration. Dataset attribution is
consolidated at `experiments/humaneval-plus/NOTICE.md`.

Current HumanEval+ strategy/router evidence, all three-worker routing traces and
accounting, current recovery/MBPP+/BigCodeBench banks, manuscript sources and every
referenced paper figure are preserved. The archived figure variants have no
byte-identical matches among referenced manuscript figures. Complete negative
results, censoring, raw-coverage limitations and interim disclosures remain.

## Validation contract

Readiness now checks the named core bundles and their recorded evidence, instead
of requiring an obsolete global count of six paper-supporting folders. Missing
bundles, empty evidence, absent classifications and broken local links still fail.
The experiment index is required to contain nine maintained bundles.

Verified after the move: `make check` passed 261 tests with five optional skips;
all 18 pilot-runtime tests passed with the optional EvalPlus environment. Both
calibration generators ran from outside the checkout and produced eight panels;
the three-worker replay produced three more. Saved pilot, HumanEval+ recovery,
MBPP+ and BigCodeBench audits passed. All 27 relocated data/figure files match
their original bytes. Optional sandbox tests use trusted fixtures; no historical
candidates, provider calls, full training or cluster experiments were rerun.

## Obsolete tooling and guide cleanup — 25 October 2026

The old anonymous supplementary ZIP builder and standalone best-parameter merger
are retired. The builder assumed a removed campaign path, old test and figure
locations, and an earlier panel layout. The merger used a superseded parameter
list and duplicated the maintained `agent-workflow merge` pipeline. Its
`run_merge_phase.py` compatibility entrypoint remains supported.

The AutoResearch family `catalog.md` and local `reproducibility.md` were
near-duplicate pointers. The family README and central reproduction guide remain
the entrypoints. Root `NOTES.md` is replaced by protocol and runtime notes in the
Qwen frontier and retry-allocation READMEs, alongside their configurations.

These five retired files remain recoverable from the parent of this maintenance
commit, `e2a5172345df02e23e74dd9556fa6be9c82e4cf6`. Generated navigation and
command maps are refreshed; the retired artifact-builder safety rule is removed.
All nine experiment bundles, their recorded evidence, frozen sources, manuscript
assets and supported runtime modes remain intact.

## Final data cleanup — 25 October 2026

Removed 73 files (1,038,492 bytes): superseded n=34, pre-router, 60-run partial
and n=10 calibration exports; the campaign-only snapshot plotter; scheduler
stdout/stderr and an empty finalize log; the cancelled, quarantined HumanEval+
partial shard; and editor settings. The n=34 and n=10 export directories,
scheduler-log directory, quarantine tree and editor-settings directory are
retired. Their complete contents are recoverable from the pre-cleanup provenance
tag described in [repository history](../history-merge.md).

Accepted raw records, complete negative outcomes, receipts, frozen sources,
protocol amendments, split/selection boundaries, canonical accounting and paper
assets remain intact. The obsolete plotter depended on a removed cluster
campaign directory; maintained figure generators use the retained evidence.
Two commands for previously removed scripts were dropped from the routing guide.

Documentation now distinguishes the primary 300-record pooled AutoResearch
accounting from the 270-record balanced sensitivity. No recorded number, cohort
or result was changed to make those distinct panels agree.
