# step1_induction — self‑contained Step 1 package

Drop this folder into the repo as **`swebench/step1_induction/`**. It is self‑contained: the
agent needs nothing outside this folder except the sibling `swebench/` tree (for reusable harness
patterns) and the repo `.venv`.

## Contents

- **`PROMPT.md`** — the operating brief to hand to the agentic coder (Codex / GPT‑5.5 XHIGH).
  You can also rename it `AGENTS.md` so Codex auto‑loads it on session start.
- **`PLAN.md`** — the authoritative Step‑1 specification: an online, verifier‑guided induction of
  a task‑bespoke orchestration on **HumanEval**. Source of truth; the agent reads it in full.

## How to launch

Give the agent `PROMPT.md` as its instruction; it reads `PLAN.md` from the same folder and builds
the `experiments/humaneval-plus/verifier-guided-dag-induction-smoke/` tree here. Heavy runs (the full online loop over HumanEval‑164) are **emitted as
commands + an `sbatch` template** for you to launch under SLURM — the agent will not submit jobs
or run the full loop itself.

## Two things to remember

1. **`canonical_solution` is used only in offline diagnostics, never in solving.** This is what
   keeps the reported pass@1 comparable to the benchmark.
2. **Verify the FlowMind (2602.11782) and TDAG (2402.10178) arXiv IDs** before relying on them —
   both come from earlier notes.
