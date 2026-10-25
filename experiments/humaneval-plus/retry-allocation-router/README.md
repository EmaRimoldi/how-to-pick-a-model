# Retry-Allocation Router on HumanEval+

This completed study learns/evaluates a five-fold allocation of ten attempts
across the 1.5B, 7B, and 32B worker traces. The bundle includes folds, router
decisions, a processed summary, configs, and launchers.

```bash
uv run python -m src.estimate_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.plot_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
```

Rerunning router decisions requires the configured Codex CLI/API backend.
