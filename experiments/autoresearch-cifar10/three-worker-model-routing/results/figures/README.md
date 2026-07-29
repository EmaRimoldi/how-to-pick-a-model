# AutoResearch Figure Set

This directory contains the curated reader-facing figures for the AutoResearch
model-routing experiment. Obsolete pilot, two-worker, deployment-accounting, and
internal diagnostic plots were removed from this folder to keep the result set
focused.

## Kept Figures

- `threeworker_relative_improvement_trajectories.{pdf,png}`: how validation
  loss changes as AutoResearch proposes sequential code edits.
- `first_hit_ecdf_by_mode.{pdf,png}`: how quickly different model/mode groups
  reach the improvement threshold.
- `threeworker_improvement_distribution.{pdf,png}`: final improvement
  distribution across MLP, compact CNN, and micro-ResNet workloads.
- `threeworker_tau_distribution.{pdf,png}`: distribution of the first
  successful proposal step.
- `threeworker_threshold_sensitivity.{pdf,png}`: whether conclusions depend on
  the chosen success threshold.
- `threeworker_router_paired_gain.{pdf,png}`: paired comparison between routed
  choices and fixed worker choices.
- `threeworker_router_selection_regret.{pdf,png}`: how much quality is left on
  the table when the router chooses the wrong worker.
- `threeworker_negative_controls.{pdf,png}`: control checks for whether router
  signals are stronger than simple baselines.

## Story Supported By These Figures

The experiment is best presented as an AutoResearch workload study, not as a
general agent-evaluation claim. The data show that iterative code-editing runs
can improve small neural-network training outcomes, but the useful worker/model
depends on the workload and on when success is measured. The router diagnostics
are useful because they expose the problem: choosing the right worker is
measurable, but the current live routing signal is still not strong enough to be
the headline result.

The strongest public story is:

1. AutoResearch produces measurable optimization progress over proposal steps.
2. Different workloads prefer different workers, so orchestration is a real
   experimental variable.
3. Success-by-budget is more informative than a single final score.
4. Routing is promising as an analysis problem, but not yet a solved product
   claim.

## Removed As Obsolete

- Pilot and partial snapshots: `init_diagnostics`, `nostop_partial_snapshot`,
  `pilot_costs`, `current_protocol_overview`.
- Two-worker plots superseded by the three-worker experiment: all `twomodel_*`.
- Raw/internal diagnostics superseded by the curated plots: all `diag_*`.
- Deployment/composite-cost and certified-resource plots, because the public
  framing now focuses on AutoResearch behavior rather than deployment-loss
  accounting.
- Older router-weight visualizations for specific model labels:
  `gpt54_*`, `gpt55_*`, `router_shift_lookup_summary`, and
  `router_true_mode_mass_comparison`.
