# HumanEval+ Experiments

- [`qwen-model-size-frontier/`](qwen-model-size-frontier/): Qwen2.5-Coder
  1.5B/7B/32B worker traces and retry frontier estimation.
- [`retry-allocation-router/`](retry-allocation-router/): five-fold router that
  allocates a ten-attempt budget across the three workers.
- [`strategy-by-difficulty-grid/`](strategy-by-difficulty-grid/): full
  model-by-strategy grid, routing analysis, and four-term accounting.
- [`llm-router-context-search/`](llm-router-context-search/): validation-only
  selection over model/context settings followed by a held-out test evaluation.
- [`verifier-guided-dag-induction-smoke/`](verifier-guided-dag-induction-smoke/):
  experimental DAG induction and per-node verifier pipeline; incomplete.

The bundles share the general-purpose pipeline under the repository's `src/`
package but own their experiment-specific data and configuration.
