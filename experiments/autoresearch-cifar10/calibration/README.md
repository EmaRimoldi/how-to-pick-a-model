# AutoResearch calibration

**Status**: completed supporting calibration, April 2026.

This bundle establishes the CIFAR-10 starting point and measurement controls.
It combines the two former calibration bundles; their recorded protocols and
scores remain separate rather than pooled into one experiment.

| Component | Evidence | Method and assets |
| --- | --- | --- |
| Starting-model selection | 161 controlled evaluations; selection uses 1,170 optimizer updates | [Methods](starting-model.md), [task rationale](task_warrant.md), [tables](results/starting-model/tables/), [figures](results/starting-model/figures/) |
| Evaluator repeatability | Five fixed-seed/fixed-step checks with identical recorded loss | [Methods](evaluation-controls.md), [original records](results/evaluation-controls/evaluator_determinism/determinism_verification.json) |
| Compute allocation | Fixed-time CPU scaling and fixed-step sequential/parallel controls | [Methods](evaluation-controls.md), [fixed-time measurements](results/evaluation-controls/fixed_time_cpu_scaling/), [fixed-step measurements](results/evaluation-controls/fixed_step_cpu_pair_benchmark/) |

These are measurement controls, not evidence that a particular agent workflow or
memory design is superior. Distinct baseline scores reflect their recorded
protocols. Exploratory 585-update calibration runs do not enter the 1,170-update
baseline-selection claims.

Regenerate figures from recorded data, without training, API credentials or GPUs:

```bash
uv run python experiments/autoresearch-cifar10/calibration/scripts/plot_baseline.py \
  --output-dir /tmp/how-to-pick-a-model-starting-calibration
uv run python experiments/autoresearch-cifar10/calibration/scripts/plot_evaluation_protocol_calibration.py \
  --output-dir /tmp/how-to-pick-a-model-evaluation-controls
```

The [experiment cleanup](../../../docs/audits/experiment-cleanup.md) records the
archived memory/pilot material and path changes. The later routing study is in
[three-worker-model-routing](../three-worker-model-routing/).
