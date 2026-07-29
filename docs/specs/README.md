# Implementation Specs

These files are historical implementation specifications for benchmark and
router work inherited from the earlier model-routing track. They are useful when
an agent needs to understand intended contracts, schemas, and launch
conventions, but they are not the current source of truth for completed result
status.

Use this order:

1. Check `experiments/README.md` for the current status of each bundle.
2. Check the specific experiment bundle README for available evidence and
   missing artifacts.
3. Use these specs only to understand the intended implementation contract.

| Spec | Purpose | Current bundle |
| --- | --- | --- |
| `ROUTER_SPEC.md` | HumanEval+ retry-allocation router contract. | `experiments/humaneval-plus/retry-allocation-router/` |
| `MBPP_SPEC.md` | MBPP+ dataset-swap contract. | `experiments/mbpp-plus/qwen-model-size-frontier/` |
| `CATEGORY_SPEC.md` | MBPP+ algorithmic-category mode-labeling contract. | `experiments/mbpp-plus/category-router-smoke/` |
| `BBH_SPEC.md` | BBH heterogeneous-subtask frontier contract. | `experiments/bbh/` |
| `EXPERIMENT_SPEC.md` | Generic experiment-implementation contract. | `experiments/` |

Do not infer that a spec is complete evidence. Status is governed by
`experiments/README.md` and the bundle-local README.
