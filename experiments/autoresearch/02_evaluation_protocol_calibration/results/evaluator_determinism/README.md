# Evaluator Determinism Appendix

**Status**: preserved protocol appendix
**Question**: can the evaluator be made deterministic enough that later agent
workflow comparisons measure agent edits rather than training noise?

## What Was Run

This appendix used fixed-step evaluation, repeated baseline checks, and early
memory/no-memory calibration reps. Its most important result is that five
unmodified baseline runs produced identical `val_bpb = 0.811222`.

## What It Contributed

The appendix established that deterministic evaluation was possible, but it also
found design problems: memory anchoring, run-count thresholds, task ceiling
effects, and training-time confounds. Those findings motivated the later
[`03_agent_memory_ablation/`](../../../03_agent_memory_ablation/) experiment.

## Read First

- [`evaluator_determinism_summary.md`](evaluator_determinism_summary.md)

## Caveat

This is not a standalone public experiment. It is methodological evidence inside
`02_evaluation_protocol_calibration/` explaining why the later ablation used a
stricter evaluation protocol.
