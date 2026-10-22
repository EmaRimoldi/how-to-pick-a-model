# Agent Guide

## Scope and reading order

The project studies cost-aware continue/restart/switch/stop decisions on
verifiable tasks. Read:

1. `README.md` and `docs/decision-protocol.md` for scope and implementation status.
2. `docs/knowledge-map.md` for code and evidence locations.
3. `docs/reproducibility.md` for safe commands and live-run prerequisites.
4. `experiments/README.md` and each relevant bundle README for evidence status.
5. `docs/paper-evidence-map.md` and `docs/paper-revision-playbook.md` for manuscript work.
6. Generated inventory, knowledge, experiment, and command maps in `docs/audits/`.

## Canonical areas

| Area | Role |
| --- | --- |
| `autoresearch/` | CIFAR-10 edit/verify benchmark and accounting |
| `experiments/autoresearch-cifar10/` | Calibration, memory, and routing baseline evidence |
| `experiments/humaneval-plus/` | Completed retry, strategy, and context-routing evidence |
| `experiments/mbpp-plus/context-value-transfer/` | Focused, prospectively frozen cross-benchmark recovery replication |
| `src/vao/` | Verified execution, model adapters, and observable run records |
| `src/agent_workflow/` | Existing baseline CLI, instrumentation, and reporting |
| `src/*.py` | HumanEval+ worker traces and routing analysis |
| `paper/neurips-submission/` | Existing manuscripts and their referenced figures |
| `paper/neurips-submission/archive/theory_anchor.tex` | Consolidated theory source |
| `artifacts/raw/` | Raw campaign archives, not runnable source |

## Safe defaults

- Prefer inspection before edits. Do not launch live model, Claude Code,
  Codex, Slurm, Docker, or provider-backed experiments unless explicitly asked.
- Use `docs/audits/command-manifest.md` before unfamiliar commands.
- Keep local outputs under ignored paths such as `runs/`, `tmp/`, or `/tmp/`.
- Preserve retained evidence, raw archives, and manuscript anchors unless the
  user explicitly approves their deletion.
- Current logs cannot establish outcomes for unobserved continuation actions.
  Do not present planned forecasters or handoff experiments as implemented.
- The context-value bundle now includes a limited trained one-checkpoint selector
  and an amended producer-transfer evaluation. Read its report and limitations;
  this does not establish a general multi-step controller or a robust method gain.
- The MBPP+ replication uses the previously observed 51 HumanEval+ failures as
  training data. Never describe the former evaluation set as a fresh holdout
  again, or pool protocols to manufacture independent task counts. Read its
  frozen protocol before collection and preserve all selected missing states.
- Existing CLI modes are baseline execution tools, not evidence of an optimal
  multi-agent architecture or a state-conditioned controller.

## Editing and verification

Update the closest README and the evidence map when retiring a bundle. Preserve
canonical experiment outputs when vendoring an actively referenced paper figure.
Keep `main.tex`, `arxiv.tex`, and `archive/theory_anchor.tex` separate.

After cleanup, run `make indexes` and `make check`. Use `make paper-build` after
changing paper assets when TeX Live is available. The build is out of tree.

```bash
uv sync --dev --frozen
make check
uv run agent-workflow demo --output-dir /tmp/how-to-pick-a-model-demo
make paper-figures-autoresearch
```

Live runs require isolated workspaces, a declared budget, and preserved configs,
usage records, artifacts, verifier feedback, and provenance.
