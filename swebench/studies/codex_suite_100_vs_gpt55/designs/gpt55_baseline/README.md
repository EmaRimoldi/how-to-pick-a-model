# GPT-5.5 Baseline Design

This directory contains the frozen single-worker baseline design for the
100-instance SWE-bench Verified comparison.

`orchestration_design.json` is strict JSON and is consumed by the executor. It
defines one universal orchestration, `gpt55_single_worker_baseline_v1`, with a
single `gpt55_direct_patcher` component. Every instance is sent to the
`codex_gpt_5_5_baseline` worker for one patch attempt. There is no router,
reviewer, retry loop, or fallback branch.

Use this design to measure the cost and resolved rate of a strong single-model
baseline under the same executor, dataset slice, and verifier workflow used by
the routed Codex-suite orchestration.
