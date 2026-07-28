# Neutral SWE-Bench 100 Trial

This study contains the self-contained, prompt-safe inputs for a fresh
100-instance SWE-bench Verified trial. It intentionally does not contain a
previous frozen orchestration or a previous matched baseline design.

## Layout

Canonical inputs:

- `study.yaml` records the canonical study paths.
- `loss_config.yaml` is the source of truth for the deployment loss weights.
- `configs/` contains the neutral meta-design config and neutral worker menu.
- `designs/` is empty until a new trial materializes a fresh design.
- `prompts/` contains the meta-designer prompt template and runtime prompt notes.
- `data/verified_100/` contains the prompt-safe 100-instance slice.

Generated outputs:

- `runs/<run_id>/` contains generated prompts, predictions, traces, manifests,
  summaries, and ephemeral `checkouts/`.
- `evaluations/<run_id>/` contains verifier outputs for that run.
- `slurm/` contains Slurm scripts and stdout/stderr for submitted jobs.

The generated-output directories are intentionally empty after cleanup. The next
Slurm launch should recreate run-specific files there.

For low-bias meta-design runs, start from
`configs/swebench_meta_design_neutral.yaml`. It treats worker aliases as
available capabilities; the meta-orchestrator must infer the deployable
structure from the instance distribution and return one `orchestration`.
The meta-design call now returns a provenance package first. The executor-facing
`orchestration_design.json` is extracted from that package and remains a clean
single-orchestration design.

Expected meta-design artifacts:

- `distribution_analysis.json`: latent modes, reusable routines, leakage risks,
  and anti-overfit checks inferred from public instances.
- `candidate_orchestrations.jsonl`: candidate policies considered during
  meta-design search.
- `candidate_loss_estimates.json`: four-term loss estimates for candidates.
- `selected_orchestration_rationale.md`: why the selected policy won.
- `orchestration_design.json`: clean design consumed by the executor.

## Current Entrypoint

```bash
PYTHONPATH=src:swebench/src:swebench \
  .venv/bin/python -m vao.swebench_orchestration.prompt \
  --config swebench/studies/neutral_swebench_trial_100/configs/swebench_meta_design_neutral.yaml \
  --instances swebench/studies/neutral_swebench_trial_100/data/verified_100/instances_public.jsonl \
  --output-dir swebench/studies/neutral_swebench_trial_100/runs/<run_id>/meta_design
```

Add `--invoke-codex` only when the next design call should actually be made.

## Artifact Retention

Keep durable, run-specific evidence after real runs:

- submitted config snapshots;
- prompt snapshots;
- `run_manifest.json`;
- `predictions.jsonl`;
- trace JSONL files;
- verifier manifests and reports;
- comparison summaries.

Delete failed smoke-test artifacts after extracting the useful lesson into a
README, manifest, or issue note. Repository `checkouts/` inside a run are
disposable once predictions, traces, executor manifests, verifier manifests, and
comparison summaries have been preserved.
