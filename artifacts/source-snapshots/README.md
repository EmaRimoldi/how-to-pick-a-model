# Source working-tree snapshots

This directory preserves files that existed in the source working trees but
were not part of their Git commits. They are retained for provenance rather
than used as the canonical runnable source.

## Contents

- `agentops-local-untracked/` contains the three local `agentops-lab-public`
  files whose exact bytes did not occur in the unified tree. Their original
  relative paths are preserved. Twenty-nine other untracked files were already
  byte-identical to files in the unified repository and are not duplicated.
- `cluster-python-cache/` contains the five ignored CPython 3.13 bytecode files
  found in the cluster checkout. They are archival, platform-specific files and
  are not imported by the project.

The cluster `.vscode/settings.json` is retained at the repository root. The 22
generated Step 1 outputs are retained in
`experiments/humaneval-plus/verifier-guided-dag-induction-smoke/` at their
natural `data/` and `logs/` paths.

The raw AutoResearch campaigns are stored separately as Git LFS archives under
`artifacts/raw/autoresearch-campaigns/`.
