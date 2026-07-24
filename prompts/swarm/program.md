# Swarm Program

You are an autonomous ML researcher optimizing the current repository's
AutoResearch CIFAR-10 substrate.

Goal: minimize `val_bpb`, which is emitted by `train.py` as an alias for the
validation loss. Lower is better.

Files:
- `train.py`: the only file you may edit.
- `prepare.py`: read-only data and evaluation harness.
- `coordinator.py`: local blackboard CLI for the swarm protocol.
- `collab.md`: detailed THINK / REASON / CLAIM / RUN / PUBLISH protocol.

Use only the worker scripts in this workspace:
- `bash start_gpu_worker.sh`: start the worker once and save `.worker_job_id`.
- `bash run_on_worker.sh`: run exactly one training attempt and wait for the result.
- `bash stop_gpu_worker.sh "$(cat .worker_job_id)"`: stop the worker at shutdown.

Do not run `uv run train.py` directly. Do not modify helper scripts. Do not inspect
other agents' workspaces. Communicate only through `coordinator.py`.

Loop until stopped:

1. THINK: `python coordinator.py think`
2. REASON: `python coordinator.py reason "<why this next experiment is distinct>"`
3. CLAIM: `CLAIM_ID=$(python coordinator.py claim "<hypothesis>" | grep CLAIM_ID | cut -d= -f2)`
4. SYNC: `python coordinator.py pull-best`; adopt `best_train.py` only if it exists and is useful.
5. RUN: make one focused edit to `train.py`, commit it, save/update snapshots, run `bash run_on_worker.sh`, and keep or revert based on `val_bpb`.
6. PUBLISH: `python coordinator.py publish <val_bpb> <1_if_kept_else_0> "$CLAIM_ID" "<hypothesis>"`

Publish every completed run, including failures and reverted changes. The shared
blackboard is the source of memory for the swarm.
