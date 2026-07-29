# AutoResearch Experiment Catalog

| Folder | Question | Evidence | Limitation |
| --- | --- | --- | --- |
| [`starting-model-calibration/`](starting-model-calibration/) | Which starting model leaves measurable optimization headroom? | 161 controlled evaluations, tables, summary, figures | calibration, not an agent comparison |
| [`evaluation-protocol-and-compute-calibration/`](evaluation-protocol-and-compute-calibration/) | Which evaluation protocol yields comparable runs? | determinism checks, fixed-step benchmark, CPU-scaling data, figures | compute-contention evidence is CPU-only |
| [`shared-memory-ablation/`](shared-memory-ablation/) | Does shared memory reduce destructive exploration? | 11 valid trials, 247 training attempts, statistical summary, figures | one execution per trial |
| [`swarm-vs-independent-agents/`](swarm-vs-independent-agents/) | How did blackboard swarms compare with independent agents? | summaries, analysis scripts, tables, figures | some historical raw run trees are absent |
| [`three-worker-model-routing/`](three-worker-model-routing/) | Can routing among three workers improve deployment accounting? | 270 processed records, 180 balanced raw traces, accounting and figure artifacts | first 90 balanced raw traces are unavailable |

SWE-bench is intentionally catalogued separately under
[`../swebench-verified/`](../swebench-verified/); it is not an AutoResearch
experiment.
