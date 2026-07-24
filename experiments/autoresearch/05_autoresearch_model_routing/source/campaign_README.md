# AutoResearch CIFAR-10 Campaign H20 Delta005

Canonical campaign root for the V3 protocol.

Parameters:
- Horizon: `H=20`
- Success threshold: relative validation-loss improvement `delta=0.05`
- Checker budget: `AUTOSEARCH_MAX_STEPS=256`
- Trajectory policy: no early stop; reconstruct first hit and occupancy offline
- Workers: `gpt_5_3_codex_spark`, `gpt_5_3_codex`, `gpt_5_4`
- Modes: `cnn_compact`, `mlp_flat`, `resnet_micro`

Layout:
- `manifests/`: scheduler array TSV manifests.
- `runs/worker_confirmation/`: holdout trajectories used for the checked raw bundle.
- `router/`: router decision JSONL files.
- `accounting/`: success, latency, token, confidence-interval, and residual diagnostics.
- `config_snapshot/`: configs and prompts used at launch.

Non-canonical earlier roots are left in place for debugging only:
- `runs/autoresearch_cifar10/slurm_pilot`
- `runs/autoresearch_cifar10/slurm_pilot_h20`
- `runs/autoresearch_cifar10/slurm_pilot_h20_delta005`
