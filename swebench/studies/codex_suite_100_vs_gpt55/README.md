# Codex Suite 100 vs GPT-5.5

This study contains the self-contained inputs and outputs for the 100-instance
SWE-bench Verified comparison between a routed Codex-suite orchestration and a
single-worker `gpt-5.5` baseline.

## Layout

- `study.yaml` records the canonical study paths.
- `loss_config.yaml` is the source of truth for the deployment loss weights.
- `configs/` contains executor and worker YAMLs used by this study.
- `designs/` contains frozen orchestration JSON designs.
- `prompts/` contains the meta-designer prompt template and runtime prompt notes.
- `data/verified_100/` contains the prompt-safe 100-instance slice.
- `runs/<run_id>/` contains generated predictions, traces, manifests, summaries,
  and ephemeral `checkouts/`.
- `evaluations/<run_id>/` contains verifier outputs for that run.
- `slurm/` contains Slurm scripts and stdout/stderr for submitted jobs.

Checkouts are disposable after a run finishes because predictions, traces,
executor manifests, evaluation manifests, and comparison summaries are the
durable artifacts.

## Current Entrypoint

```bash
STUDY_ROOT=swebench/studies/codex_suite_100_vs_gpt55 \
  bash swebench/scripts/submit_codex_suite_100_vs_gpt55_slurm.sh
```

The launcher defaults to this `STUDY_ROOT`, so the environment variable is only
needed when running a variant study.
