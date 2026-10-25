Research task for AGENT_ID={{AGENT_ID}} in RUN_ID={{RUN_ID}} (experiment: {{EXPERIMENT_ID}}).
Assigned role: {{AGENT_ROLE}}.

Setup is already complete:
- You are already on branch: {{BRANCH}}
- Your current working directory is exactly: `{{WORKSPACE}}`
- `train.py`, `prepare.py`, and all required files are in your current directory.
- Data is already present (symlinked from the shared data directory).

Stay inside `{{WORKSPACE}}` for the entire run. Do not inspect or mention any other
repository path, and do not ask for external GPU access. Use only the local worker
scripts in this workspace.
Do not modify or delete any helper scripts in this workspace. `train.py` is the only
file you may edit.

**Before the loop — read the in-scope files once for full context:**
```bash
cat README.md    # repository context and project overview
cat prepare.py   # fixed constants, data loading, evaluation — do NOT modify
cat train.py     # the file you modify: architecture, optimizer, hyperparameters, training loop
```
Then initialize `results/results.tsv` with just the header row.

Session parameters:
- Time budget: {{TIME_BUDGET}} minutes
- Evaluator budget: {{EVALUATOR_BUDGET_DESCRIPTION}}
- Evaluator concurrency: {{EVALUATOR_CONCURRENCY}}
- Pre-registered success threshold q*: {{TARGET_VAL_BPB}}
- Environment vars: RUN_ID={{RUN_ID}} AGENT_ID={{AGENT_ID}}

WORKFLOW — follow this exactly:

**Step 0 (once, before anything else):**
```
if [ -f .worker_job_id ]; then
  WORKER_JOB_ID=$(cat .worker_job_id)
else
  WORKER_JOB_ID=$(bash start_gpu_worker.sh)
  echo "$WORKER_JOB_ID" > .worker_job_id
fi
echo "Worker: $WORKER_JOB_ID"
```
This allocates a dedicated {{COMPUTE_DEVICE}} for your entire session. Do it once and keep $WORKER_JOB_ID.

**This first turn is baseline-only:**
1. Run the baseline on the unmodified `train.py`
2. Append the result to `results/results.tsv`
3. Do **not** start a second experiment in this same turn
4. Return a short summary of the baseline result and the most promising next hypothesis

**At end (only if explicitly told the session is ending):**
```
bash stop_gpu_worker.sh $WORKER_JOB_ID
```

Your first run should establish the baseline: run step 0, then run `bash run_on_worker.sh` on the unmodified `train.py`, log the result, and stop.

Do NOT use git merge commands or try to access other agents' workspaces.
Do NOT pause to ask the human if you should continue.
After the baseline is logged, stop and wait for the next controller turn.

Start now.
