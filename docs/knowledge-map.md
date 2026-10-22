# Knowledge Map

The current research direction is defined in [decision protocol](decision-protocol.md).
The retained studies provide baselines. The
[OpenRouter development pilot](../experiments/humaneval-plus/openrouter-continuation-pilot/README.md)
adds a one-checkpoint collector and small development dataset; learned policies
and held-out validation remain future work.

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

Use `experiments/README.md` and bundle-local READMEs before citing results.

## Code

- `src/vao/orchestrator.py`, `src/vao/schemas.py`: execution and observable state.
- `src/vao/agents/`: model adapters and supported session behavior.
- `src/vao/decisions/`: budgeted OpenRouter calls, observable checkpoints,
  isolated public-example feedback and evaluation-only EvalPlus scoring.
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
