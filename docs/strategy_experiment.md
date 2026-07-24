# Mode-specialized strategy experiment

## Scientific objects

- Models: Qwen2.5-Coder 1.5B, 7B, and 32B.
- Modes: the frozen HumanEval+ reference-length tertiles.
- Strategies: direct, structured plan-and-check, and robust decomposition.
- Mapping: easy -> direct, medium -> structured, hard -> robust.
- Resource clocks: generated tokens (primary) and wall-clock seconds (secondary).
- Router signal `Z^(n)`: held-out task plus `n` cross-fitted labeled examples.
- Router outputs: a posterior over modes and an integer retry allocation over the
  corresponding strategies.

Every worker model runs every strategy on every task. This full factorial is
needed to test whether the strategy bank is actually specialized rather than
assuming diagonal competence.

## Stages

1. `src.run_strategy_eval` writes resumable attempt-level worker logs.
2. `src.run_strategy_router` writes held-out posteriors and allocations for
   context sizes 0, 5, and 20.
3. `src.analyze_strategy_experiment` estimates focused `t0`, model throughput
   `kappa`, competence ratios, and the inverse-share slope.
4. `src.analyze_strategy_router` performs fold-held-out temperature calibration
   and estimates `G`, routing KL mismatch, and effective mode count.

## Cluster

- Root: `/orcd/data/tpoggio/001/erimoldi/theory-of-agents-strategy`
- Shared model cache: `/orcd/data/tpoggio/001/erimoldi/huggingface`
- Worker jobs: eight shards per model on H100 GPUs.
- Pilot: three balanced tasks, three strategies, two attempts, 1.5B model.

The full launcher is gated:

```bash
CONFIRM_FULL_RUN=YES ./scripts/submit_strategy_full.sh
```

Before submission, the three model snapshots must be present in the shared
cache so GPU jobs never spend allocation time downloading weights.
