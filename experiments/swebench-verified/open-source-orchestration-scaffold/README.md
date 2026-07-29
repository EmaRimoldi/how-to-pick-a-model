# Open-Source SWE-bench Orchestration

This study contains the open-source worker orchestration scaffold: meta-design
configs, worker configs, and prompt-safe data manifests.

The tracked scaffold assets are under:

- `configs/`
- `data/`

New launchers write run artifacts under `runs/` when executed; those runtime
directories are not pre-populated in this scaffold.

Some historical configs refer to design artifacts that must be regenerated or
provided explicitly before launching a Slurm pilot.
