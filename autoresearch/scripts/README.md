# AutoResearch Scripts

These scripts support the AutoResearch CIFAR-10 experiment family. They should
be read together with `autoresearch/README.md`,
`docs/reproducibility.md`, and
`experiments/autoresearch-cifar10/three-worker-model-routing/README.md`.

## Safe Reproduction Scripts

- `reproduce_main_figures_from_processed.py`: regenerate main paper figures
  from processed three-worker analysis JSON.
- `reproduce_appendix_figures_n20_confirmation.py`: regenerate appendix figures
  from official n=20 confirmation raw runs.
- `plot_autoresearch_certified_resource.py`: generate certified-resource paper
  figures.
- `plot_autoresearch_router_shift_lookup_summary.py`: summarize router
  mode-shift and lookup-calibrated choices.
- `plot_autoresearch_router_weight_shift.py`: plot posterior/allocation shifts.

These are the preferred scripts for reviewer-facing regeneration from checked-in
evidence.

## Analysis And Accounting

- `analyze_autoresearch_threeworker_final.py`
- `analyze_autoresearch_allocation_router.py`
- `compute_autoresearch_factored_calibration.py`
- `generate_autoresearch_current_plots.py`

Use these when changing accounting, threshold, calibration, or routing analysis
for the AutoResearch paper.

## Campaign And Cluster Helpers

- `generate_autoresearch_campaign_tasks.py`
- `run_autoresearch_allocation_router_batch.sh`
- `run_autoresearch_cifar10_cnn4096_router_test.sh`
- `run_threshold_calibration_array_task.sh`
- `run_z_probe_array_task.sh`
- `slurm_autoresearch_worker_array.sh`

These can launch live or cluster-backed work. Do not run them unless explicitly
requested and after checking the target config, output root, model access, and
compute environment.

## Artifact Builder

- `make_neurips2026_artifact.py`: whitelist-based anonymous supplementary ZIP
  builder.

The artifact builder writes under `dist/` and should be checked before sharing
any generated archive.
