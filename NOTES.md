# Notes

- Project root: the current repository directory is treated as the root of the spec's `proper-time-frontier/` tree.
- Backend: Ollama, via the local HTTP API at `http://localhost:11434`.
- Dataset and verifier: the implementation uses the `evalplus` Python package for HumanEval+ data and official plus checks. This avoids reimplementing the pass criterion and still uses the EvalPlus HumanEval+ release.
- Difficulty proxy: default `ref_solution_length`, using a deterministic regex token count over `canonical_solution`. Tertiles are rank-based to keep mode sizes near 55 problems each.
- Censoring: raw logs keep unsolved tasks as `tau_tokens=Infinity` and `solved=false`. They also record `tokens_generated_total`, the finite censoring budget used by Kaplan-Meier.
- Estimation: `tau_star.json` includes raw bootstrap intervals for plotting; `frontier.json` includes bootstrap CIs for winner-vs-runner log2 ratios, which determine `separated`.
- Full-run ETA is deliberately rough and controlled by `EXPECTED_TOKENS_PER_ATTEMPT` and `TOKENS_PER_SECOND` environment variables.

## Router experiment notes

- Worker traces: the router experiment consumes only the three existing full-run JSONL files. No Qwen worker is re-run.
- Success threshold: strict `attempt_statuses[i] == "pass"` only. `pass/fail`, `fail/pass`, and `fail/fail` are failures.
- Simulator: `execute_allocation` consumes attempts sequentially in the fixed order `1.5b -> 7b -> 32b` and charges every consumed attempt up to and including the first pass.
- Attempt arrays: logs store per-attempt data as parallel arrays (`attempt_seconds`, `attempt_token_counts`, `attempt_statuses`), not nested objects.
- Allocation guard: if an allocation asks for more attempts than are logged for a model, the simulator consumes only the logged attempts. This matters mainly after a solved trace, because worker logs stop at first pass.
- Oracle allocation: for unsolved-by-all problems, the hindsight oracle returns a zero-attempt unsolved allocation. This is an upper-bound convention because the oracle knows no worker can solve the problem from the logged attempts.
- Statistical oracle: implemented as a training-fold, mode-conditional empirical optimizer over all allocations with total attempts `<= 10`. It uses only training tasks with the same mode, chooses the lowest mean-time allocation that matches the best single model's training solved rate for that mode, and falls back to max solved rate if no allocation meets the target.
- Router backend: `codex_cli` by default, using local Codex ChatGPT subscription auth. `ROUTER_MODEL=gpt-5.4` with `reasoning_effort: medium` is the selected full-run router configuration.
- Router prompt: real router calls prefer full training traces. If the serialized prompt exceeds the internal character guard, the router falls back to a per-mode summary; the smoke path uses only the mock router.
- Codex CLI router isolation: each router call runs from a temporary directory with workspace-write sandboxing and receives the training traces in the prompt. This avoids giving the router filesystem access to held-out worker logs.
- Full router run: `experiments/humaneval-plus/retry-allocation-router/scripts/full_router_run.sh` estimates 164 total router calls before execution.
