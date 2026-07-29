# Shared SWE-bench Runtime

This is the implementation shared by the SWE-bench Verified experiment
bundles. It is not itself a result bundle.

- `src/vao/swebench_orchestration/`: download, prompt/meta-design, execution,
  repository-context, failure-analysis, meta-update, and official-evaluation
  modules.
- `scripts/`: Slurm/vLLM launcher.
- `tests/`: orchestration unit and fixture tests.
- `runtime/`: ignored local cache/checkouts and ad-hoc outputs created on demand.

Use this import path from the repository root:

```bash
export PYTHONPATH="$PWD/src:$PWD/experiments/swebench-verified/shared-runtime/src:$PWD"
```

The Slurm launcher defaults heavyweight Hugging Face/vLLM assets to
`$SLURM_TMPDIR` when available. Its default study config is the sibling
`open-source-orchestration-scaffold`; callers must provide a design artifact.
