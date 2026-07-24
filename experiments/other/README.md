# Other experiments

This directory contains all experiment artifacts that are not part of the
AutoResearch/CIFAR-10 track.

- [`strategy-routing-runs/`](strategy-routing-runs/): completed strategy worker,
  closure, and router-search evidence.
- [`mbpp-category-smoke/`](mbpp-category-smoke/): MBPP category-routing smoke
  figures.
- [`swebench-experimental-scaffold/`](swebench-experimental-scaffold/):
  SWE-bench study scaffold; not a completed result bundle.

The HumanEval+, MBPP+, and BBH logs used by the legacy proper-time pipeline are
stored in the root `data/` directory. Their configs are in `config/`, their
analysis modules are the root-level `src/*.py` files, and their reproducibility
matrix is in
[`../../docs/reproducibility-other-experiments.md`](../../docs/reproducibility-other-experiments.md).
