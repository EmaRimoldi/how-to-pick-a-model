# NeurIPS_2026 cluster merge audit

## Source

- Cluster checkout:
  `/home/erimoldi/openclaw_remote/projects/NeurIPS_2026`
- Former remote:
  `https://github.com/EmaRimoldi/distribution-aware-orchestration.git`
- Source branch and commit:
  `main` at `96895081a506620471c6a13722957b5843e79595`
- Destination:
  `EmaRimoldi/how-to-pick-a-model`

The former GitHub remote no longer resolves. The source commit and all of its
ancestors were fetched directly from the cluster checkout and retained as the
second parent of the integration merge.

## Tree comparison

The source commit contains 420 tracked paths. Compared with the destination
`main` used for the merge:

- 97 paths occur at the same location;
- 89 of those paths are byte-identical;
- 8 differ, primarily unified-repository metadata and documentation;
- 323 exist only at the source path;
- 102 of those source-only paths have byte-identical content elsewhere in the
  unified tree.

The destination versions of `.gitignore`, the top-level README, package
metadata, requirements, and unified config documentation were retained. These
files describe the combined project rather than the former standalone package.

## Imported material

- Unique AutoResearch legacy modules and the artifact builder were added to the
  root `autoresearch/` package.
- Six unique historical router figures were added to the AutoResearch figure
  archive.
- `step1` became
  `experiments/humaneval-plus/verifier-guided-dag-induction-smoke/`.
- SWE-bench code, scaffolds, and dated evidence were split into the four named
  bundles under `experiments/swebench-verified/`.
- `Archive/stateful_query_engine` was moved to
  `experiments/archive/stateful-query-engine/` and labelled as a historical
  benchmark implementation because it contains no result, report, or run artifacts.
- The original source README and diagnostic memo were copied to `docs/archive/`.

## Deliberate exclusions

- `paper_overleaf` was not reintroduced as a submodule. Its checked-out commit,
  `07ca9d8`, is already an ancestor of the imported manuscript history under
  `paper/`.
- The source `.gitmodules` file was omitted with that redundant submodule.
- The source `uv.lock` was not substituted for the unified repository lock.
- Generated `vao_query_optimization.egg-info/`, ignored caches, virtual
  environments, and local run outputs were excluded.
- Byte-identical runtime, test, and figure copies were not duplicated.

## Working-tree snapshot

At audit time the cluster checkout also had tracked changes and untracked
files beyond source commit `9689508`:

- 32 tracked changes, of which 31 belonged to `swebench/` and one was the
  redundant `paper_overleaf` submodule pointer;
- 23 untracked files, of which 16 belonged to a new SWE-bench study, one was a
  root lock file, and six were generated package metadata.

The integration overlays all 31 tracked SWE-bench changes, including source
deletions, and all 16 untracked SWE-bench study files. The resulting imported
SWE-bench snapshot contains 94 files. The submodule pointer, source lock file,
and generated package metadata remain excluded for the reasons above.

## Validation

- SHA-256 comparison confirmed that all 94 imported SWE-bench files match the
  live cluster working tree.
- Checksum comparison confirmed that `Archive`, `step1`, and the imported
  AutoResearch legacy modules match source commit `9689508`.
- High-confidence credential scans found no secrets in the staged tree or the
  imported Git history.
- Python compilation, shell syntax, JSON parsing, and YAML parsing completed
  successfully for the imported material.
- The unified root suite passed 159 tests; the imported SWE-bench suite passed
  21 tests; the AutoResearch reproduction suite passed 5 tests.
- All three archived PDF figures are valid one-page PDFs and their PNG
  counterparts have valid image headers.
