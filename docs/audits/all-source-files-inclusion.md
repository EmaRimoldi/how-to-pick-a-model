# Source working-tree inclusion audit

Date: 2026-07-28

This audit records the material added after the repository-history merge at
`71aeb45200d55c326aee685b04313bdc85c62764`. The purpose is to preserve files
that existed outside the source Git commits without making raw or
platform-specific artifacts part of the canonical runtime.

## Cluster working tree

- The 22 ignored Step 1 outputs from
  `NeurIPS_2026.pre-unified-step1-generated-backup-20260728` are present at the
  corresponding `experiments/humaneval-plus/verifier-guided-dag-induction-smoke/`
  `data/` and `logs/` paths.
- The ignored AutoResearch campaign is preserved in 18 Git LFS component
  archives under `artifacts/raw/autoresearch-campaigns/`.
- The campaign archives contain 191,525 tar entries: 123,704 regular files,
  67,551 directories, and 270 symbolic links. Their compressed size is
  20,926,391 bytes.
- All 250 worker-confirmation run directories are present exactly once. The
  sorted source and archive run-name inventories both have SHA-256
  `70b2a5a8a6a2010bd02af7462a2ee78ddd59e692012646e6746fcd678b43131f`.
- The cluster `.vscode/settings.json` is retained at the repository root.
- Five ignored CPython 3.13 cache files are retained under
  `artifacts/source-snapshots/cluster-python-cache/`. The ignored cluster
  `tmp/` directory was empty.

## Mac working trees

The requested `theory-of-agents` working-tree state was applied on top of the
unified repository: five modified tracked files, 102 tracked deletions, and the
untracked root `manuscript.tex`. The manuscript wrapper has SHA-256
`9ec086fe2abd99b759884d508361978f857f1122cad54ccc12febbb228e3de3e`.

The `agentops-lab-public` checkout contained 32 untracked files. Twenty-nine
were already byte-identical to canonical files in the unified tree. The three
remaining exact source versions are retained, with their original relative
paths, under `artifacts/source-snapshots/agentops-local-untracked/`. They do not
replace the canonical versions because the source copies contain absolute Mac
paths or the pre-merge experiment layout.

## Integrity and validation

- `artifacts/raw/autoresearch-campaigns/SHA256SUMS` verifies all 18 LFS parts.
- `artifacts/source-snapshots/SHA256SUMS` verifies the 31 directly retained
  working-tree files: 22 Step 1 outputs, five Python cache files, three
  `agentops-lab-public` source copies, and `.vscode/settings.json`.
- A high-confidence credential scan found no API keys, GitHub tokens, AWS keys,
  or populated provider-secret assignments in the retained files or archive
  streams.
- All added Step 1 JSON and JSONL files parse successfully.
- The affected Python scripts compile successfully.
- `manuscript.tex` compiles to a 35-page PDF.
- The unified test suite passes: 159 tests.
