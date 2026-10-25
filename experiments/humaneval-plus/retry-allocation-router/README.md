# Retry-Allocation Router on HumanEval+

This completed study learns/evaluates a five-fold allocation of ten attempts
across the 1.5B, 7B, and 32B worker traces. The bundle includes folds, router
decisions, a processed summary, configs, and launchers.

```bash
uv run python -m vao.humaneval.estimate_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m vao.humaneval.plot_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
```

## Trace replay and baselines

The [router config](configs/router.yaml) consumes the three existing full-run
logs and frozen modes from the [Qwen frontier](../qwen-model-size-frontier/README.md).
Replay does not rerun Qwen workers. Run commands from the repository root.

- Only `attempt_statuses[i] == "pass"` counts as success. Mixed `pass/fail`
  and `fail/pass` statuses, and `fail/fail`, count as failures.
- Logs store parallel `attempt_seconds`, `attempt_token_counts` and
  `attempt_statuses` arrays. The simulator consumes attempts in the fixed order
  `1.5b → 7b → 32b` and charges each consumed attempt through the first pass.
  An allocation cannot consume more attempts than were logged; solved worker
  traces stop at their first pass.
- The hindsight oracle assigns zero attempts to tasks unsolved by all logged
  workers. This is an upper-bound convention using knowledge of their outcomes.
- The statistical oracle uses training-fold tasks of the same mode, falling
  back to the full training fold if that mode is absent. It searches allocations
  totalling at most ten attempts and minimizes mean time subject to matching
  the best single model's training solved rate. If none meet the target, it
  maximizes training solved rate.

## Router collection

The recorded full run contains 164 `codex_cli` decisions with `gpt-5.4` and
medium reasoning effort. The config reads the model from `ROUTER_MODEL`;
rerunning decisions requires the configured Codex CLI/API backend and its
authentication. This is separate from replaying recorded decisions.

Real router prompts prefer full training traces, falling back to a per-mode
summary above the 180,000-character guard. Codex calls run from temporary
directories with workspace-write sandboxing and receive training material in
the prompt; held-out worker logs are not placed in those directories. The
smoke path uses the mock router and is not an empirical result.

`scripts/full_router_run.sh` estimates 164 total router calls before execution.
Use it only for an explicitly authorized new run in an isolated copy: the
launcher resumes or writes the configured result path. See the central
[reproduction guide](../../../docs/reproducibility.md) for dependencies and
live-run requirements.
