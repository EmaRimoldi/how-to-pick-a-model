# Distribution-aware orchestration import

This directory preserves the non-AutoResearch material from the former
`distribution-aware-orchestration` repository and its cluster checkout:

`/home/erimoldi/openclaw_remote/projects/NeurIPS_2026`

The imported Git history ends at source commit
`96895081a506620471c6a13722957b5843e79595`. The merge commit that added this
directory has that source commit as a parent, so the original history remains
queryable with normal Git commands.

## Contents

- `Archive/stateful_query_engine/`: historical stateful-query-engine benchmark,
  configs, analysis, and tests.
- `step1/`: HumanEval induction, routing, oracle, and adaptation artifacts.
- `swebench/`: later SWE-bench orchestration studies and their implementation.

The shared `src/vao/` runtime was not duplicated here: its files already exist
at the repository root and were byte-identical at the source commit. Some
cluster-era configs intentionally use paths relative to this snapshot root, so
run them from this directory while exposing both source locations on
`PYTHONPATH`, for example:

```bash
repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root/experiments/other/distribution-aware-orchestration"
PYTHONPATH="$repo_root/src:swebench/src:swebench:$repo_root" \
  uv run --project "$repo_root" --frozen pytest swebench/tests -q
```

## AutoResearch boundary

AutoResearch additions from the same checkout are kept in the root
`autoresearch/` package and under `experiments/autoresearch/`. They are not
mixed into this non-AutoResearch snapshot.

See `docs/audits/neurips-2026-cluster-merge.md` for the deduplication and
exclusion decisions.
