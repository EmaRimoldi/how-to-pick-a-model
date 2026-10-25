# Qwen Model-Size Frontier on HumanEval+

This completed worker study contains one 164-task JSONL log for each of
Qwen2.5-Coder 1.5B, 7B, and 32B, plus the estimated modes, success curves,
frontier, and retry thresholds.

Regenerate processed results with:

```bash
uv run python -m src.estimate --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
uv run python -m src.plot --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
```

## Protocol and recorded outputs

- Workers use Ollama's local HTTP API at `http://localhost:11434` and the
  official EvalPlus HumanEval+ dataset and plus checks.
- The default difficulty proxy, `ref_solution_length`, counts regex tokens in
  `canonical_solution`. Rank-based tertiles assign roughly 55 tasks to each mode.
- Unsolved raw records keep `tau_tokens=Infinity` and `solved=false`.
  `tokens_generated_total` gives their finite censoring budget for Kaplan–Meier
  estimation; an unsolved trace is not an observed successful completion.
- `tau_star.json` retains bootstrap intervals for plotting. `frontier.json`
  records winner-versus-runner log2-ratio intervals; `separated` requires the
  upper end of the 95% interval to be below zero.

The [retry-allocation study](../retry-allocation-router/README.md) consumes these
saved worker logs directly.

The full and smoke launchers are under `scripts/`. They require Ollama, model
weights and the optional `other-experiments` dependencies described in the
[reproduction guide](../../../docs/reproducibility.md). They execute new model
attempts; run them only for an explicitly authorized new experiment in an
isolated copy. `full_run.sh` estimates runtime using
`EXPECTED_TOKENS_PER_ATTEMPT` and `TOKENS_PER_SECOND`; this is a rough ETA.
