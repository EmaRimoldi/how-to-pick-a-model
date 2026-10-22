# OpenRouter continuation pilot

Status: development protocol and runner; no learned controller or held-out gain.

Qwen3.5 9B and 27B use the same `siliconflow/fp8` endpoint without fallbacks.
Size is an experimental attribute, not an intelligence measurement or a causal
intervention that holds pretraining and post-training fixed.

## Frozen protocol

- HumanEval+ v0.1.10, EvalPlus 0.3.1, dataset MD5
  `fe585eb4df8c88d844eeb463ea4d0302`.
- Shuffle numerically ordered tasks with executable public-docstring examples
  using seed `20261022`; take 24. Eligibility uses public prompts, never model
  outcomes. This favors doctest-style documentation and does not represent the
  full benchmark. Exclude these tasks from future held-out controller evaluation.
- One initial 9B attempt and two independent direct 27B attempts per task.
  Temperature 0.6, maximum 1536 output tokens, reasoning disabled, JSON with a
  complete Python solution. SiliconFlow does not advertise a sampler seed, so
  none is sent. Local seeds fix selection/order, not generation; save requests.
  Reference solutions must pass visible and full tests before spending.
- Visible feedback uses only examples already in the prompt. Compare equivalent
  Python literals despite quote-style differences; a public predicate without
  printed output is required to evaluate to True. Full EvalPlus base/plus scores
  never trigger branches or appear in feedback.
- Passing visible examples stops a policy, including false positives subsequently
  found by EvalPlus. On visible failure, sample two continuations per action:
  9B repair, 9B fresh restart, 27B fresh restart, 27B repair with the original
  transcript/public feedback. Both repair actions receive identical messages.
  Interleave controls and branch draws in a frozen shuffled order.
- Repeats share an exact parent checkpoint; they are not independent tasks.
  Compare only fully observed matched tasks. Learned multi-checkpoint policies
  and length-matched context controls are future work. This pilot does not
  establish controller superiority or causal informative-context gains.

## Cost and execution

Explicit budget: at most **2 USD**. Each serial call reserves its worst-case
token charge at the configured price ceilings: 16,384 input and 1536 output
tokens. UTF-8 message bytes plus a framing allowance must fit the input ceiling.
Requests require FP8, supported parameters, maximum prices and no fallbacks.
Preflight checks real credit and exact endpoint availability/prices.

Ceilings in USD per million tokens: 9B input/output 0.10/0.15; 27B 0.25/2.00.
Stream completions with keepalive support and record the final authoritative
`usage.cost`, token/cache/reasoning details, provider, generation
ID, latency, messages and output. Invalid/truncated output is charged and scored
as failure. Unknown billing keeps its reservation and stops; no automatic retry
or resume of an existing journal is allowed. Unexpected over-ceiling receipts
are recorded and halt further calls. The bound relies on provider enforcement
of requested token and price limits.

Policy cost includes the prefix once plus the chosen action. Collection cost
pays for all counterfactual draws. Record verifier time separately without an
invented dollar conversion. The small development sample supports no held-out
gain, optimality or statistical-significance claim.

```bash
uv sync --dev --extra continuation-pilot --frozen
uv run python scripts/run_continuation_pilot.py \
  --config experiments/humaneval-plus/openrouter-continuation-pilot/configs/pilot.json \
  --output runs/continuation-plan
```

Default: write a task/config manifest with no model calls. An explicitly
authorized paid run adds `--live --budget-usd 2` and a fresh output directory.
Supply `OPENROUTER_API_KEY` in the local environment, or use `--key-stdin`.
Never put credentials in arguments, configs, tracked files or transcripts.

Live verification currently requires **macOS sandbox-exec**. It clears child
credentials, denies network and user-home/other-temporary-workspace reads,
allows OS/interpreter/library reads and run-local writes, bounds execution/output,
and probes isolation before calling models. Unsupported hosts fail closed.
Linux CI tests offline logic; a portable container backend is future work.

Outputs: `manifest.json`, append-only `budget.jsonl`, `calls.jsonl`,
`evaluations.jsonl`, `outcomes.jsonl`, `summary.json`, and `report.md`.
Curated results must exclude API keys, account identifiers and account balances.
