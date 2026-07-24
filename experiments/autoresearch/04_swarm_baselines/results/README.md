# Swarm Baseline Results

Historical analysis artifacts moved from `swarm baseline analysis/` on 2026-04-13.

Read the canonical experiment summary first:
[`../README.md`](../README.md).

These results are conceptually close to the current shared-memory experiments
because they experiment two agents optimizing `val_bpb` while sharing information.
They are historical swarm artifacts, not a direct substitute for the current
curated ablation experiments: the swarm uses a stronger blackboard protocol with
claim / publish / pull-best coordination, while the current shared-memory mode
uses a simpler shared-log and prompt-injection mechanism.

Contents:

- `figures/`: current public figures for the cleaned experiment narrative.
- `analysis/analyze_swarm.py`: archived swarm analysis script.
- `analysis/haiku_swarm_run_1_deep_dive/`: report and figures for one historical Haiku swarm run.
- `analysis/model_comparison/`: archived model comparison analysis, figures, CSV, and JSON summaries.
- `analysis/swarm_vs_independent_parallel/`: archived swarm-vs-parallel comparison, figures, and summary.

Interpretation guide:

- `analysis/swarm_vs_independent_parallel/` compares a historical independent-parallel baseline against historical 2-agent swarm runs.
- `analysis/haiku_swarm_run_1_deep_dive/` explains one swarm run through trajectory plots, shared-memory event timing, cross-agent influence, parameter exploration, and attribution.
- `analysis/model_comparison/` compares Haiku 4.5, Sonnet 4.6, and Opus 4.6 in the historical 2-agent swarm setting.
- These artifacts are useful context for the swarm blackboard implementation under `src/agentops_lab/swarm/`.
- They should be read as historical design evidence, not as a fully normalized benchmark table.

No local `swarm/runs/` directory was present when these artifacts were moved. If raw cloned swarm run directories are restored later, place them under `results/swarm/runs/` so the swarm analysis scripts resolve paths consistently.
