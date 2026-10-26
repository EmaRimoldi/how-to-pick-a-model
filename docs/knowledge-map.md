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

The user-requested [goal amendment](../experiments/python-repair/checkpoint-environment/GOAL-AMENDMENT-20261026.md)
prioritizes the value of acquiring public execution evidence before another
repair. The [offline diagnostic adapter](../experiments/python-repair/checkpoint-environment/DIAGNOSTIC-PREPARATION.md)
and [case audit / replay](../experiments/python-repair/checkpoint-environment/results/diagnostic-audit-20261026/README.md)
are implemented; no diagnostic benefit or selector advantage has been demonstrated.
The [prospective information study](../experiments/python-repair/checkpoint-environment/INFORMATION-PROTOCOL.md)
adds a 96-request frozen design and terminal-only report, with no selector fitting.
Its [first-request interruption](../experiments/python-repair/checkpoint-environment/results/information-interrupted-20261026/README.md)
retains zero responses, one uncertain reservation and 95 never-admitted requests.
The [only successor's terminal bank](../experiments/python-repair/checkpoint-environment/results/information-stopped-20261026/README.md)
retains 65 responses and 31 missing outcomes after another HTTP 429. No complete
repair was observed; the original screen is inconclusive. The report, 130 saved
evaluation records and public diagnostic projections reproduce offline.
`scripts/audit_repair_stagnation.py` reproduces the separate post hoc edit audit:
25 exact copies, 25 further entrypoint-only syntax changes, 15 other edits.
No collector is active. The [next design](../experiments/python-repair/checkpoint-environment/STAGNATION-CONTROL-DESIGN.md)
tests interface cues without adding bug facts; it enables no live calls.
The [implemented v1 interface protocol](../experiments/python-repair/checkpoint-environment/INTERFACE-PROTOCOL.md)
now fixes 128 fresh requests, a separate allocation and terminal-only factorial
analysis. `prepare_repair_interface_study.py` verifies the comment transformation
and exact projections offline; `report_repair_interface_study.py` retains all
missing cells and the declared primary contrast. The shared collector requires
a separately reviewed clean freeze and a new single-use study claim.
Its [terminal bank](../experiments/python-repair/checkpoint-environment/results/interface-stopped-20261026/README.md)
contains 44 usable responses, eleven per arm, with no complete repair. HTTP 429
leaves 84 unknown cells; the frozen screen is inconclusive. Independent replay
reproduces 88 saved evaluations. The interface collector is closed and no
successor is enabled. `plot_repair_interface.py` renders all four conditions from a terminal
report, including missingness and syntax-edit counts.

The [coding-solver compatibility control](../experiments/python-repair/checkpoint-environment/SOLVER-PROTOCOL.md)
uses `prepare_repair_solver_study.py` and `report_repair_solver_study.py` with the
same one-use collector and independent archived replay. It fixes 32 new draws
on eight already exposed failures, keeps original public messages, and checks
repeated full repairs with Qwen3-Coder-Next before any separate policy study.
Its [complete bank](../experiments/python-repair/checkpoint-environment/results/solver-qwen-20261026/README.md)
has ten full repairs in 32 attempts and meets the repeated-success screen on
three bugs; 62 saved evaluation records reproduce independently. All collectors
are closed. `plot_repair_solver.py` renders the complete planned grid;
`audit_repair_trigger_coverage.py` independently checks the twelve closed source
candidates and their conditional acceptance ceiling. The next stage is a new
intervention calibration. No causal cross-model comparison, acquisition advantage
or selector training is established.

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


The subsequent [matched Qwen public-trace study](../experiments/python-repair/checkpoint-environment/results/information-qwen-stopped-20261026/README.md)
closed on a connection timeout with 18/64 responses: nine per arm, three trace
and two focused full repairs. Forty-six cells remain unknown; primary bounds
are −68.75 to +75.00 percentage points, mean/bootstrap null and gate inconclusive.
All 36 saved evaluations and public diagnostic projections reproduce. This is
neither evidence of benefit nor a null effect. The operative selector goal is
active, with no selector fit, retry or continuation of this bank.
