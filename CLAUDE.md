# How to Pick a Model

Read `AGENTS.md`, `docs/decision-protocol.md`, and `docs/knowledge-map.md` first.
The current scope is cost-aware sequential decisions on verifiable tasks.

Existing AutoResearch and HumanEval+ experiments are baseline evidence. The
state-conditioned continuation/handoff policy is planned work. Do not imply
that old traces evaluate unobserved actions or establish a new method's gains.

Use `docs/reproducibility.md` and the command safety manifest. Do not start live
model or cluster runs unless explicitly requested. Before an existing live CLI
baseline, run `uv run agent-workflow doctor`; use isolated workspaces and
fixed-step evaluation with a serialized evaluator for comparable claims.

Keep new work in the retained benchmark families, with an explicit README,
inputs, configs, status, and evidence boundary. Do not revive retired benchmark
scaffolds incidentally during cleanup. Historical material is recoverable via
`docs/history-merge.md`.

Run `make check` after changes and `make paper-build` after changing paper assets.
