# Knowledge Map

The current research direction is defined in [decision protocol](decision-protocol.md).
The retained studies provide baselines. The
[OpenRouter development pilot](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md)
adds a one-checkpoint collector and small development dataset.
The [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md)
adds a code/feedback factorial and prospective zero-shot forecasts. Its separate
[frozen transfer protocol](../experiments/humaneval-plus/context-value/VALIDATION.md)
implements development-trained task/state ridge baselines, prospective API
forecasts and budgeted replay on task-disjoint, different-producer failures.
The general multi-step controller remains future work.
The [audited transfer report](../experiments/humaneval-plus/context-value/results/validation-20261022/report.md)
and [blog draft](blog/when-to-keep-failed-code.md) give the current results and limits.

## Evidence

| Question | Bundle |
| --- | --- |
| Fair starting model | `experiments/autoresearch-cifar10/starting-model-calibration/` |
| Evaluator and compute confounds | `experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/` |
| Context/memory baseline | `experiments/autoresearch-cifar10/shared-memory-ablation/` |
| Model choice and first-hit accounting | `experiments/autoresearch-cifar10/three-worker-model-routing/` |
| Worker model-size frontier | `experiments/humaneval-plus/qwen-model-size-frontier/` |
| Retry allocation | `experiments/humaneval-plus/retry-allocation-router/` |
| Strategy routing | `experiments/humaneval-plus/strategy-by-difficulty-grid/` |
| Context selection with held-out evaluation | `experiments/humaneval-plus/llm-router-context-search/` |
| Value of failed code versus public feedback | `experiments/humaneval-plus/context-value/` |

Use `experiments/README.md` and bundle-local READMEs before citing results.

## Code

- `src/vao/orchestrator.py`, `src/vao/schemas.py`: execution and observable state.
- `src/vao/agents/`: model adapters and supported session behavior.
- `src/vao/decisions/`: budgeted OpenRouter calls, observable checkpoints,
  isolated public feedback and evaluation-only EvalPlus scoring.
- `src/vao/decisions/recovery_policy.py`: frozen, inexpensive probability baselines.
- `src/vao/decisions/recovery.py`: development/frozen-evaluation collection.
- `src/vao/decisions/recovery_import.py`: explicit phase transitions and preserved charges/reservations.
- `scripts/analyze_recovery_validation.py`: offline receipt/provenance audit and finite policy replay.
- `src/agent_workflow/`: baseline CLI, snapshots, cost/trace collection, reports.
- `autoresearch/benchmark/cifar10/`: workloads and verifier.
- `autoresearch/analysis/`, `autoresearch/scripts/`: accounting and reproduction.
- `src/load_traces.py`, `src/execute.py`, `src/simulate.py`: HumanEval+ traces,
  verification, and retry replay under its declared assumptions.
- Other root `src/*.py` modules: retained HumanEval+ estimation and routing.

The next controller belongs around observable edit/verify checkpoints; it must
not assume access to private reasoning states. See the decision protocol before
adding interfaces or claiming offline replay can evaluate new handoffs.

## Manuscripts and navigation

`paper/neurips-submission/main.tex` and `arxiv.tex` retain existing manuscripts.
`paper/neurips-submission/archive/theory_anchor.tex` retains consolidated theory.
Only referenced paper figures are vendored; canonical evidence stays in bundles.

Use `docs/paper-evidence-map.md` for claim boundaries,
`docs/audits/theory-consolidation.md` for historical proof caveats, and generated
maps in `docs/audits/` for retrieval. Retired sources remain in Git history.
