# Experiments

This directory is the empirical spine of AutoResearch Orchestration. Each
numbered folder is one evidence bundle: the question, what was run, the result,
the caveat, and the file a reviewer should read first.

![Experiment map](../docs/assets/experiments/experiment-map.png)

## Reading Order

1. [`01_baseline/`](01_baseline/) - selects the common starting `train.py`.
2. [`02_evaluation_protocol_calibration/`](02_evaluation_protocol_calibration/) - proves
   why later comparisons must use deterministic, fixed-step evaluation.
3. [`03_agent_memory_ablation/`](03_agent_memory_ablation/) - tests memory and
   exploration in agent workflows.
4. [`04_swarm_baselines/`](04_swarm_baselines/) - summarizes blackboard
   swarm evidence.
5. [`05_autoresearch_model_routing/`](05_autoresearch_model_routing/) - contains
   AutoResearch routing/accounting results and raw trace coverage.
6. [`06_swebench_experimental_scaffold/`](06_swebench_experimental_scaffold/) -
   contains SWE-bench scaffold inputs and implementation code, without results.

For a compact table of every experiment bundle, read
[`catalog.md`](catalog.md).

For exact rerun commands, dependency profiles, and limitations, read
[`reproducibility.md`](reproducibility.md).

## Experiment Bundles

| Experiment | Role | What was run | Main result | Read first |
| --- | --- | --- | --- | --- |
| [`01_baseline/`](01_baseline/) | Starting point calibration | 161 controlled evaluations of candidate starting models and edits | selected starting model: `val_bpb = 0.841354`, target `<= 0.824` | [`01_baseline/README.md`](01_baseline/README.md) |
| [`02_evaluation_protocol_calibration/`](02_evaluation_protocol_calibration/) | Evaluation protocol | deterministic evaluator checks, fixed-time CPU scaling, fixed-step pair benchmark, archived 2x2 pilot | fixed-step evaluation removes training noise; fixed-time parallel comparisons can measure hardware contention instead of agent quality | [`02_evaluation_protocol_calibration/README.md`](02_evaluation_protocol_calibration/README.md) |
| [`03_agent_memory_ablation/`](03_agent_memory_ablation/) | Current agentic signal | 11 valid trials, memory/exploration/seeding variations | shared memory stabilized exploratory search: `T07` best `0.914`, mean `1.049` vs `T06` best `0.933`, mean `1.816` | [`03_agent_memory_ablation/README.md`](03_agent_memory_ablation/README.md) |
| [`04_swarm_baselines/`](04_swarm_baselines/) | Historical swarm context | two-agent blackboard swarm runs and model comparisons | swarm runs reached lower `val_bpb` than the independent parallel baseline | [`04_swarm_baselines/README.md`](04_swarm_baselines/README.md) |
| [`05_autoresearch_model_routing/`](05_autoresearch_model_routing/) | Model-routing results | 270-run processed AutoResearch routing/accounting bundle, figures, config snapshots, and minimal raw traces | 263/270 processed runs crossed the 5% threshold; 180 balanced records have checked-in raw traces | [`05_autoresearch_model_routing/README.md`](05_autoresearch_model_routing/README.md) |
| [`06_swebench_experimental_scaffold/`](06_swebench_experimental_scaffold/) | Scaffold | neutral 100-instance SWE-bench input slice, configs, prompts, and orchestration implementation | scaffold only; no completed SWE-bench result bundle yet | [`06_swebench_experimental_scaffold/README.md`](06_swebench_experimental_scaffold/README.md) |

## Vocabulary

- **Experiment**: one evidence bundle under `experiments/`.
- **Trial**: one valid configuration inside an experiment. The agent-memory
  ablation experiment uses a compact `T01`-`T11` index.
- **Wave**: an execution batch inside an experiment. It is scheduling metadata, not a
  public milestone.
- **Successful training attempt**: a run that produced a valid evaluator result,
  not a separate experiment.
- **Confirmatory run**: a future run with fixed-step evaluation, retained raw
  logs, and a pre-registered success threshold.

## Completeness

The public tree keeps curated summaries, result tables, and figures. Raw run
directories, transient agent workspaces, local datasets, and large private logs
are intentionally left out unless an experiment explicitly says otherwise.
