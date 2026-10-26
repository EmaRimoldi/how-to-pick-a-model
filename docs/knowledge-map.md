# Knowledge Map

Completed feedback-only stage: [protocol, exact task manifest and results](../experiments/bigcodebench/feedback-only-routing/README.md),
`src/vao/decisions/feedback_routing.py` (fixed trajectories), `bigcode.py` and
`bigcode_worker.py` (reference qualification and isolated verification),
`scripts/analyze_feedback_routing.py` (frozen receipt/prompt audit and paired analysis),
`scripts/verify_feedback_evidence.py` (published hashes, statistics, frozen sources,
verifier-repeat record and original interim-prefix preservation). All 157 task
clusters/628 policy outcomes observed; primary escalation gain not established.
See the [research note](blog/feedback-only-escalation.md) for measured admission
and verifier limitations; no new selector is trained.

The current research direction is defined in [decision protocol](decision-protocol.md).
The retained studies provide baselines. The
[initial pilot provenance](../experiments/humaneval-plus/context-value/provenance/continuation-pilot/README.md)
retains historical billing, task exclusions and the shared collector configuration.
The [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md)
adds a code/feedback factorial and prospective zero-shot forecasts. Its separate
[frozen transfer protocol](../experiments/humaneval-plus/context-value/VALIDATION.md)
implements development-trained task/state ridge baselines, prospective API
forecasts and budgeted replay on task-disjoint, different-producer failures.
The general multi-step controller remains future work.
The focused [MBPP+ replication](../experiments/mbpp-plus/context-value-transfer/README.md)
tests transfer to a fresh benchmark and adds a feedback-only predictor ablation.
Its [audited results](../experiments/mbpp-plus/context-value-transfer/results/replication-20261022/README.md)
and [separate empirical paper](paper/recovery-value/README.md) retain 94/96
complete failures and no established primary gain, with missing-state bounds.
The [audited transfer report](../experiments/humaneval-plus/context-value/results/validation-20261022/report.md)
and [blog draft](blog/when-to-keep-failed-code.md) give the current results and limits.

## Evidence

| Question | Bundle |
| --- | --- |
| Worker model-size frontier | `experiments/humaneval-plus/qwen-model-size-frontier/` |
| Retry allocation | `experiments/humaneval-plus/retry-allocation-router/` |
| Strategy routing | `experiments/humaneval-plus/strategy-by-difficulty-grid/` |
| Context selection with held-out evaluation | `experiments/humaneval-plus/llm-router-context-search/` |
| Value of failed code versus public feedback | `experiments/humaneval-plus/context-value/` |

Use `experiments/README.md` and bundle-local READMEs before citing results.

## Code

- `src/vao/schemas.py`, `src/vao/records.py`: observable run records.
- `src/vao/decisions/`: budgeted OpenRouter calls, observable checkpoints,
  isolated public feedback and evaluation-only EvalPlus scoring.
- `src/vao/decisions/recovery_policy.py`: frozen, inexpensive probability baselines.
- `src/vao/decisions/recovery.py`: development/frozen-evaluation collection.
- `src/vao/decisions/recovery_import.py`: explicit phase transitions and preserved charges/reservations.
- `scripts/analyze_recovery_validation.py`: offline receipt/provenance audit and finite policy replay.
- `src/vao/humaneval/load_traces.py`, `src/vao/humaneval/execute.py`, `src/vao/humaneval/simulate.py`: HumanEval+ traces,
  verification, and retry replay under its declared assumptions.
- Other `vao/humaneval/` modules: retained HumanEval+ estimation and routing.

The next controller belongs around observable edit/verify checkpoints; it must
not assume access to private reasoning states. See the decision protocol before
adding interfaces or claiming offline replay can evaluate new handoffs.

## Manuscripts and navigation

`docs/paper/neurips-submission/main.tex` and `arxiv.tex` retain existing manuscripts.
`docs/paper/neurips-submission/archive/theory_anchor.tex` retains consolidated theory.
Only referenced paper figures are vendored; canonical evidence stays in bundles.

Use `docs/paper-evidence-map.md` for claim boundaries,
`docs/audits/theory-consolidation.md` for historical proof caveats, and generated
maps in `docs/audits/` for retrieval. Retired sources remain in the [provenance history](history-merge.md).

CIFAR-10 and its dedicated runtime are archived; historical manuscript figures
point to their [provenance](history-merge.md).

## Current Python repair calibration

The [checkpoint environment](../experiments/python-repair/checkpoint-environment/README.md)
retains the incomplete recovery pilot and both output-contract diagnostics.
The [complete DeepInfra diagnostic](../experiments/python-repair/checkpoint-environment/results/contract-deepinfra-20261026/README.md)
contains all 36 calls, frozen requests, inert source evidence and independent
sandbox reproduction. No format met the calibration gate; no repair selector
has been trained. These twelve bugs are development-exposed.

The [complete 12B capability diagnostic](../experiments/python-repair/checkpoint-environment/results/contract-gemma12b-20261026/README.md)
also fails the unchanged gate despite more usable outputs. All36 calls and72
verifier records are preserved and independently reproduced; no recovery or
selector gain is inferred from this initial-repair study.

The [27B capability control](../experiments/python-repair/checkpoint-environment/results/contract-gemma27b-20261026/README.md)
is complete too: 36 responses, three successes on two distinct bugs, unchanged
gate failed. Independent execution reproduced all 72 saved verification records.
The [post hoc capability comparison](../experiments/python-repair/checkpoint-environment/results/capability-comparison-20261026/README.md)
separates syntax validity, partial test progress and full repairs; it preserves
FP8/BF16 confounding, regressions and public-test false positives. No repair
selector or scaling law is demonstrated.
