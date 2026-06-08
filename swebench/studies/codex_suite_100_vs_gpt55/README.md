# Codex Suite 100 vs GPT-5.5

This study contains the self-contained inputs and outputs for the 100-instance
SWE-bench Verified comparison between a routed Codex-suite orchestration and a
single-worker `gpt-5.5` baseline.

## Layout

Canonical inputs:

- `study.yaml` records the canonical study paths.
- `loss_config.yaml` is the source of truth for the deployment loss weights.
- `configs/` contains executor and worker YAMLs used by this study.
- `designs/` contains frozen orchestration JSON designs.
- `prompts/` contains the meta-designer prompt template and runtime prompt notes.
- `data/verified_100/` contains the prompt-safe 100-instance slice.

Generated outputs:

- `runs/<run_id>/` contains generated predictions, traces, manifests, summaries,
  and ephemeral `checkouts/`.
- `evaluations/<run_id>/` contains verifier outputs for that run.
- `slurm/` contains Slurm scripts and stdout/stderr for submitted jobs.

The generated-output directories are intentionally empty after cleanup. The next
Slurm launch should recreate run-specific files there.

For low-bias meta-design runs, start from the neutral config in
`configs/swebench_orchestration_codex_suite_meta_design_neutral.yaml`. It treats
worker aliases as available capabilities, not planner/reviewer/router roles; the
meta-orchestrator must infer reusable latent structure from the instance
distribution and return one deployable `orchestration`.

## Current Entrypoint

```bash
STUDY_ROOT=swebench/studies/codex_suite_100_vs_gpt55 \
  bash swebench/scripts/submit_codex_suite_100_vs_gpt55_slurm.sh
```

The launcher defaults to this `STUDY_ROOT`, so the environment variable is only
needed when running a variant study.

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
