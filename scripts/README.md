# Repository Scripts

## Navigation and validation

- `build_repo_inventory.py`: retained-tree inventory, with logical LFS sizes.
- `build_knowledge_index.py`: code, theory, experiment, and active-reference map.
- `build_experiment_manifest.py`: assets and reproducibility status by bundle.
- `build_command_manifest.py`: command prerequisites and safety classes.
- `validate_agent_readiness.py`: generated-map freshness, core evidence,
  references, duplicate policy, and local-path/link checks.
- `agent_index_config.py`: shared configuration, not a command entrypoint.
- `check_paper_build.py`: out-of-tree build of both retained manuscripts.

```bash
make indexes
make check
make paper-build
```

## Existing baseline helpers

`analyze_runs.py`, `compare_experiments.py`, `benchmark_parallel_capacity.py`,
`run_single_long_experiment.py`, `run_parallel_experiment.py`,
`run_merge_phase.py`, and `run_best_params_merge.py` support the existing CLI
baseline runtime. Launch helpers may invoke live models or compute; use the
command safety manifest and explicit run authorization.

`bootstrap_engaging.sh` is a historical HumanEval+ cluster environment helper.
Current portable setup is documented in `docs/reproducibility.md`.

AutoResearch reproduction and campaign commands live under `autoresearch/scripts/`.
