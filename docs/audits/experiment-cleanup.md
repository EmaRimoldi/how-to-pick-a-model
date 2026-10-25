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
