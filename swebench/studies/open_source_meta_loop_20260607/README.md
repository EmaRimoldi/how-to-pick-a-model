# Open-Source Meta-Loop 2026-06-07

This study preserves the useful artifacts from the historical worktree
`/home/erimoldi/openclaw_remote/projects/.worktrees/swebench-real-20260606-103655`.

It is an archive for mechanistic analysis, not the active launcher for the
current Codex-suite 100-instance experiment.

## What This Study Captures

- A one-instance hierarchical loop on `sympy__sympy-16886` that eventually
  resolved through a meta-orchestrator-selected `public_literal_repair` policy.
- A 50-instance open-source orchestration pass that improved candidate
  generation from 0 non-empty patches to 8 apply-checkable patches, but resolved
  0 official SWE-bench instances.
- Failure-bundle evidence showing that meta-updates improve only when traces,
  repo context, patch/apply status, and verifier evidence are preserved.
- Dataset-level routing analysis over SWE-bench Verified.

## Layout

- `analysis/real_failure_modes_20260606/` contains human reports, summaries,
  and plots from the one-instance and 50-instance experiments.
- `analysis/verified_instances_20260606/` contains post-hoc dataset analysis.
  Some files use gold-patch-derived labels and must not be used in solver
  prompts.
- `configs/` contains the historical launcher/config inputs that produced the
  archived runs.
- `designs/` contains selected frozen and meta-updated orchestration designs.
- `runs/` keeps compact executor evidence: manifests, predictions, traces,
  failure bundles, meta-update outputs, and updated configs.
- `evaluations/` keeps official Modal/SWE-bench manifests and compact report
  JSON files.

## Leakage Rules

Files under `analysis/verified_instances_20260606/` are for post-hoc analysis
and routing research only. Do not inject gold-derived repair shape, gold domain
cluster, hidden tests, solution fields, private metadata, or `full_with_gold`
data into runtime solver prompts.

Prompt-safe runtime evidence is limited to public issue fields, public hints
when explicitly included by the dataset slice, repository state at
`base_commit`, model traces, local apply-check output, and official verifier
feedback.

## Key Takeaways

- `repo_context.py` reduces information loss by materializing the public repo at
  `base_commit`, ranking candidate files, and passing snippets to workers.
- `meta_update.py` turns traces, predictions, repo context, and evaluation
  manifests into a failure bundle for policy updates.
- `public_literal_repair` should be policy-gated. It was useful for the Morse
  literal case, but the 50-instance run showed it can produce false positives.
- The next optimization target is candidate quality: fewer empty patches, fewer
  invalid diffs, stricter deterministic-tool gating, and better conversion of
  localized evidence into semantically correct patches.

## Omitted From This Archive

The original worktree also contained checkout directories, vLLM logs, raw Slurm
stdout/stderr, cache-like folders, and a `full_with_gold` data copy. Those were
not copied here because they are either large, reproducible, or inappropriate as
prompt inputs.
