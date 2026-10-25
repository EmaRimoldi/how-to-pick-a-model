Swarm research task for AGENT_ID={{AGENT_ID}} in RUN_ID={{RUN_ID}} (experiment: {{EXPERIMENT_ID}}).

Your workspace is ready:
- Branch: {{BRANCH}}
- Current working directory: `{{WORKSPACE}}`
- `train.py`, `prepare.py`, `program.md`, `collab.md`, and `coordinator.py` are in the workspace.
- Data is symlinked. Worker scripts are present.
- `SWARM_MEMORY_PATH` is set in your environment and in `.swarm_env`.

Session parameters:
- Time budget: {{TIME_BUDGET}} minutes
- Training time per run: ~{{TRAIN_TIME_BUDGET_MIN}} min ({{TRAIN_TIME_BUDGET}}s plus harness overhead)

Read `program.md` and `collab.md` before making changes. They describe the swarm blackboard protocol.

Start the worker once:

```bash
if [ -f .worker_job_id ]; then
  WORKER_JOB_ID=$(cat .worker_job_id)
else
  WORKER_JOB_ID=$(bash start_gpu_worker.sh)
  echo "$WORKER_JOB_ID" > .worker_job_id
fi
echo "Worker: $WORKER_JOB_ID"
```

Every experiment iteration must follow:

```text
THINK -> REASON -> CLAIM -> pull-best -> RUN -> PUBLISH
```

Use `python coordinator.py think` to read the shared blackboard, `python coordinator.py claim "<hypothesis>"` before editing, and `python coordinator.py publish <val_bpb> <1_or_0> "$CLAIM_ID" "<hypothesis>"` after the result is known.

Do not run `uv run train.py` directly. Use `bash run_on_worker.sh`, which blocks until the current repository's training harness finishes.

Do not access other agents' workspaces directly. The blackboard is the only shared state. Continue the loop until the controller stops the session.
