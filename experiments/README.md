# Experiments

Every experiment is grouped first by benchmark and then by the concrete
question it studies. A bundle owns its configs, launchers, inputs, processed
results, figures, and run metadata whenever those artifacts are available.

| Benchmark | Experiment bundle | Status | Evidence in the repository |
| --- | --- | --- | --- |
| AutoResearch / CIFAR-10 | [`starting-model-calibration/`](autoresearch-cifar10/starting-model-calibration/) | completed | 161 controlled evaluations, tables, figures, plotting script |
| AutoResearch / CIFAR-10 | [`evaluation-protocol-and-compute-calibration/`](autoresearch-cifar10/evaluation-protocol-and-compute-calibration/) | completed | deterministic-evaluator checks, CPU scaling, fixed-step/fixed-time summaries |
| AutoResearch / CIFAR-10 | [`shared-memory-ablation/`](autoresearch-cifar10/shared-memory-ablation/) | completed | 11 trials, statistical summary, figures |
| AutoResearch / CIFAR-10 | [`swarm-vs-independent-agents/`](autoresearch-cifar10/swarm-vs-independent-agents/) | historical/partial | summaries, analyses, figures; some raw run trees absent |
| AutoResearch / CIFAR-10 | [`three-worker-model-routing/`](autoresearch-cifar10/three-worker-model-routing/) | completed with raw-coverage gap | processed 270-record accounting panel and 180 balanced raw traces |
| HumanEval+ | [`qwen-model-size-frontier/`](humaneval-plus/qwen-model-size-frontier/) | completed | three 164-task worker logs and processed frontier estimates |
| HumanEval+ | [`retry-allocation-router/`](humaneval-plus/retry-allocation-router/) | completed | folds, router decisions, summary, configs, launchers |
| HumanEval+ | [`strategy-by-difficulty-grid/`](humaneval-plus/strategy-by-difficulty-grid/) | completed | full run, source/config snapshot, raw shards, summaries, figures |
| HumanEval+ | [`llm-router-context-search/`](humaneval-plus/llm-router-context-search/) | completed | validation selection, held-out test evaluation, logs, figure |
| HumanEval+ | [`verifier-guided-dag-induction-smoke/`](humaneval-plus/verifier-guided-dag-induction-smoke/) | incomplete smoke | implementation and smoke artifacts; rep42 cheap-node coverage is 9/42 |
| MBPP+ | [`qwen-model-size-frontier/`](mbpp-plus/qwen-model-size-frontier/) | completed worker logs | three 378-task logs and mode estimates |
| MBPP+ | [`two-model-retry-router/`](mbpp-plus/two-model-retry-router/) | partial | config and folds; router result/summary files are absent |
| MBPP+ | [`category-router-smoke/`](mbpp-plus/category-router-smoke/) | smoke/partial | smoke figures and configs; full category labels/results are absent |
| BBH | [`qwen-model-size-frontier/`](bbh/qwen-model-size-frontier/) | partial frontier | two 1,200-task logs and mode files; no tracked 32B log |
| BBH | [`family-and-subtask-router/`](bbh/family-and-subtask-router/) | runnable scaffold | configs and launchers; no completed router result bundle |
| SWE-bench Verified | [`neutral-100-meta-design-scaffold/`](swebench-verified/neutral-100-meta-design-scaffold/) | scaffold | prompt-safe 100-instance slice, configs, prompts, frozen designs |
| SWE-bench Verified | [`open-source-orchestration-scaffold/`](swebench-verified/open-source-orchestration-scaffold/) | scaffold | worker/meta-design configs and prompt-safe data manifests |
| SWE-bench Verified | [`open-source-meta-loop-2026-06-07/`](swebench-verified/open-source-meta-loop-2026-06-07/) | historical result archive | official evaluation manifests, failure analyses, plots, selected designs |
| SWE-bench Verified | [`shared-runtime/`](swebench-verified/shared-runtime/) | implementation | orchestration code, Slurm launcher, and tests shared by the SWE studies |
| Historical | [`stateful-query-engine/`](archive/stateful-query-engine/) | archived benchmark | 61 implementation/config/test files; no runs, results, figures, or reports |

## Families

- [`autoresearch-cifar10/`](autoresearch-cifar10/)
- [`humaneval-plus/`](humaneval-plus/)
- [`mbpp-plus/`](mbpp-plus/)
- [`bbh/`](bbh/)
- [`swebench-verified/`](swebench-verified/)
- [`archive/`](archive/) (historical implementations, excluded from active evidence)

The former `stateful-query-engine` benchmark has been removed from the active
families and retained under `archive/`, clearly marked as an implementation
without run, result, figure, or report evidence.

Reproduction guidance lives in [`../docs/reproducibility.md`](../docs/reproducibility.md).
