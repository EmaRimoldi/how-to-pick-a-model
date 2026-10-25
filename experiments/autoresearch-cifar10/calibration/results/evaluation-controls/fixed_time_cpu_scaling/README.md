# Fixed-Time CPU Scaling Benchmark

This benchmark isolates the compute-allocation confound in the first 2x2 agent
pilot.

## Question

If several identical `train.py` jobs run on the same CPU for the same wall-clock
budget, does each worker receive less effective training compute?

## Method

- Workload: identical CPU-only `train.py` jobs.
- Budget: fixed 2-second training window per worker.
- Concurrency levels: 1, 2, 4, and 8 simultaneous processes.
- Policies:
  - `default`: each process can use the default PyTorch/OpenMP thread behavior;
  - `partitioned`: CPU cores are divided across processes.
- Metrics:
  - mean optimizer steps completed by each worker;
  - validation loss, logged as `val_bpb`;
  - group wall time, speedup, and efficiency.

## Result

Under fixed-time evaluation, increasing concurrency reduces optimizer updates per
worker and worsens validation loss. Partitioning helps at `N=2`, but degradation
returns at higher concurrency.

This is why fixed-time parallel agent comparisons are confounded: a parallel
workflow can look worse because each training worker receives less compute, not
because the agents made worse decisions.

Raw table: [`fixed_time_summary.csv`](fixed_time_summary.csv).
