# Fixed-Step CPU Pair Benchmark

## Purpose

The compute-allocation calibration already includes a fixed-time benchmark that
ran identical `train.py` jobs under a fixed 2-second wall-clock budget. That
benchmark answered one important question: when multiple training jobs share the
same CPU budget, do parallel jobs complete fewer gradient updates and therefore
produce worse validation loss?

This follow-up benchmark answers the complementary question: if each training job is forced to complete the same number of gradient updates, how much wall-clock time is lost to CPU contention? This distinction matters for interpreting the 2x2 agent experiments. Under a fixed-time evaluator, parallel agents can be penalized because each `train.py` receives less CPU time and completes fewer steps. Under a fixed-step evaluator, the number of gradient updates is equalized, so contention appears as slower evaluations rather than lower-quality evaluations.

## Method

- Source lineage: deterministic CIFAR-10 CNN training script preserved through
  `results/evaluator_determinism/`
- Training substrate: deterministic CIFAR-10 CNN training script from the
  evaluator-determinism appendix
- Device: CPU
- Fixed training length: 300 steps per worker
- Conditions:
  - `single_t4`: one training process, 4 CPU threads
  - `seq2_t4`: two training processes run sequentially, 4 CPU threads each
  - `par2_t4`: two training processes run concurrently, 4 CPU threads each
  - `par2_t2`: two training processes run concurrently, 2 CPU threads each

The benchmark imports the deterministic `train.py`, overrides `MAX_STEPS = 300`, constrains process-level thread environment variables, and records group wall time, per-worker wall time, completed steps, and validation loss.

## Results

| condition | group wall seconds | mean worker wall seconds | steps | mean val_bpb |
| --- | ---: | ---: | --- | ---: |
| `single_t4` | 86.99 | 85.88 | 300 | 1.267963 |
| `seq2_t4` | 172.44 | 85.10 | 300, 300 | 1.267963 |
| `par2_t4` | 98.48 | 97.15 | 300, 300 | 1.267963 |
| `par2_t2` | 125.86 | 124.60 | 300, 300 | 1.267963 |

## Interpretation

The fixed-step results separate compute contention from training quality. All workers completed exactly 300 steps and reached the same validation loss, so there was no loss-quality penalty once gradient updates were equalized.

There was still a wall-clock penalty. With 4 threads per process, two concurrent jobs finished in 98.48 seconds instead of the 172.44 seconds required by running the same two jobs sequentially, a 1.75x group-level speedup. However, each worker slowed from 85.10 seconds to 97.15 seconds on average, a 14.2% per-worker slowdown. This means CPU parallelism is useful for throughput at N=2, but it is not free.

The 2-thread concurrent condition was worse on this workload: group wall time was 125.86 seconds and mean worker time was 124.60 seconds. In this setup, limiting each process to 2 threads reduced useful intra-process parallelism more than it reduced inter-process contention.

The practical implication is that CPU parallel evaluation can be acceptable for two workers if the evaluator is fixed-step rather than fixed-time. Claims about agent quality should still avoid mixing fixed-time CPU-parallel runs with fixed-time single-agent runs, because the older fixed-time benchmark showed that the parallel jobs receive fewer gradient updates in the same wall-clock budget.
