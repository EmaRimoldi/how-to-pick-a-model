# How to Pick a Model

Read `AGENTS.md`, `docs/decision-protocol.md`, and `docs/knowledge-map.md` first.
The current scope is cost-aware sequential decisions on verifiable tasks.

Existing AutoResearch and HumanEval+ experiments are baseline evidence. The
context-value bundle implements simple task/state ridge selectors, prospective
API forecasts and finite one-checkpoint recovery replay. Its amended validation
tests transfer from Gemma development failures to Ministral evaluation failures;
the original same-producer validation is unavailable after upstream rate limits.
Read the frozen protocol and audited results before making performance claims.
This does not implement a general multi-step continuation/handoff controller.
Old traces cannot evaluate unobserved actions or establish a new method's gains.

Use `docs/reproducibility.md` and the command safety manifest. Do not start live
model or cluster runs unless explicitly requested. Before an existing live CLI
baseline, run `uv run agent-workflow doctor`; use isolated workspaces and
fixed-step evaluation with a serialized evaluator for comparable claims.

Keep new work in the retained benchmark families, with an explicit README,
inputs, configs, status, and evidence boundary. Do not revive retired benchmark
scaffolds incidentally during cleanup. Historical material is recoverable via
`docs/history-merge.md`.

Run `make check` after changes and `make paper-build` after changing paper assets.
