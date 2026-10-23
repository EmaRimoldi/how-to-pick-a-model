# Experiments

Completed [feedback-only fixed-policy evaluation](bigcodebench/feedback-only-routing/README.md):
157 previously unqueried, reference-qualified BigCodeBench tasks, all 628 policy
outcomes. Immediate escalation versus retry 9B is −2.55 pp [−7.01, +1.27],
95% paired interval; the primary gate fails. No new selector is trained.

Eight baseline bundles, API discovery and a frozen transfer evaluation support the sequential-decision question in
`docs/decision-protocol.md`. Each is grouped by benchmark and research question. A bundle owns its configs, launchers, inputs, processed
results, figures, and run metadata whenever those artifacts are available.

| Benchmark | Experiment bundle | Status | Evidence in the repository |
| --- | --- | --- | --- |
| AutoResearch / CIFAR-10 | [`starting-model-calibration/`](autoresearch-cifar10/starting-model-calibration/) | completed | 161 controlled evaluations, tables, figures, plotting script |
| AutoResearch / CIFAR-10 | [`evaluation-protocol-and-compute-calibration/`](autoresearch-cifar10/evaluation-protocol-and-compute-calibration/) | completed | deterministic-evaluator checks, CPU scaling, fixed-step/fixed-time summaries |
| AutoResearch / CIFAR-10 | [`shared-memory-ablation/`](autoresearch-cifar10/shared-memory-ablation/) | completed | 11 trials, statistical summary, figures |
| AutoResearch / CIFAR-10 | [`three-worker-model-routing/`](autoresearch-cifar10/three-worker-model-routing/) | completed with raw-coverage gap | processed 270-record accounting panel and 180 balanced raw traces |
| HumanEval+ | [`qwen-model-size-frontier/`](humaneval-plus/qwen-model-size-frontier/) | completed | three 164-task worker logs and processed frontier estimates |
| HumanEval+ | [`retry-allocation-router/`](humaneval-plus/retry-allocation-router/) | completed | folds, router decisions, summary, configs, launchers |
| HumanEval+ | [`strategy-by-difficulty-grid/`](humaneval-plus/strategy-by-difficulty-grid/) | completed | full run, source/config snapshot, raw shards, summaries, figures |
| HumanEval+ | [`llm-router-context-search/`](humaneval-plus/llm-router-context-search/) | completed | validation selection, held-out test evaluation, logs, figure |
| HumanEval+ | [`openrouter-continuation-pilot/`](humaneval-plus/openrouter-continuation-pilot/) | development pilot | 24 tasks, 88 calls, two failed checkpoints, receipts and separate public/full-suite scoring |
| HumanEval+ | [`context-value/`](humaneval-plus/context-value/) | discovery + producer-transfer evaluation | Discovery: 30 tasks/132 calls. Transfer: 83 development + 60 evaluation tasks, 1,353 responses, frozen policies, forecasts, controls and cost audit |
| MBPP+ | [`context-value-transfer/`](mbpp-plus/context-value-transfer/) | collection finished; censored descriptive bank | 94/96 complete failures, 2,878 recovery responses, two censored solver cells, 288 API forecasts, fixed comparisons and full accounting |
| BigCodeBench standard-library subset | [`feedback-only-routing/`](bigcodebench/feedback-only-routing/) | complete; primary gate not passed | 157 task clusters, 628/628 policy outcomes, 1,492 responses, no missing outcomes; fixed comparisons, receipts, source freeze, verifier repeat and disclosed single requested interim look |

## Families

- [`autoresearch-cifar10/`](autoresearch-cifar10/)
- [`humaneval-plus/`](humaneval-plus/)
- [`mbpp-plus/context-value-transfer/`](mbpp-plus/context-value-transfer/)
- [`bigcodebench/feedback-only-routing/`](bigcodebench/feedback-only-routing/)

The former `stateful-query-engine` implementation had no run, result, figure,
or report evidence. It was retired from the working tree and remains available
in [Git history](https://github.com/EmaRimoldi/how-to-pick-a-model/tree/d98e3f2209c6e470885e748aafb0a41ea6395291/experiments/archive/stateful-query-engine).

Reproduction guidance lives in [`../docs/reproducibility.md`](../docs/reproducibility.md).

The focused tree retires peripheral benchmark families and incomplete scaffolds.
Their history is recoverable via `docs/history-merge.md`. Historical baseline data
cannot score unobserved handoffs. The API diagnostics collect matched outcomes
under separate protocols. The frozen transfer evaluates a one-checkpoint selector;
its gain over a stronger static control remains inconclusive. It does not validate
a general multi-step controller or complete the originally planned same-producer test.
