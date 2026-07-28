# SWE-bench Real Slurm Smoke Attempts

Last updated: 2026-06-06T20:00:00Z

## Completed Runs

| job id | node | target requested | instance executed | non-empty patch | outcome |
|---|---|---|---|---:|---|
| 15537314 | node1918 | sympy__sympy-16886 | astropy__astropy-7671 | 0 | Bootstrap, vLLM, repo context, traces, and predictions completed. Patch calls failed with HTTP 400 because requested `max_tokens=12000` exceeded the remaining 16,384-token context after 11,459 input tokens. |
| 15542504 | node4309 | sympy__sympy-16886 | sympy__sympy-16886 | 1 | Successful retry after prompt-budget and instance-targeting fixes. Worker became ready, executor used the targeted single-row JSONL, and `predictions.jsonl` contained a non-empty patch for `sympy/crypto/crypto.py`. |

## Fixed Before Successful Retry

- Executor now shapes repository context by component role and computes an effective output cap from `context_window_tokens`, estimated input size, and a safety margin.
- Executor traces now include `prompt_budget` metadata for worker calls.
- Slurm launcher now honors `INSTANCES` and can materialize a single-row JSONL from `INSTANCE_ID`, preventing targeted smokes from silently using the config's first instance.
- Local targeted selection check wrote `/tmp/swebench_instance_selection_check.jsonl` and confirmed it contains `sympy__sympy-16886`.
- Local targeted dry run used `/tmp/swebench_instance_selection_check.jsonl` and reported `instances_path=/tmp/swebench_instance_selection_check.jsonl`.

## Intermittent Scheduler Problems Observed During Debugging

These scheduler issues happened during debugging, but they were temporary rather than terminal.

| time window | command class | result |
|---|---|---|
| 2026-06-06T17:18Z | `sbatch` real SymPy smoke submission | Failed before job creation: unable to contact Slurm controller. |
| 2026-06-06T17:20Z | `sinfo` / `squeue` probes | Both hung and then reported controller contact failure or timed out. |
| 2026-06-06T17:23Z | local endpoint probe | Ports 8000-8003 were closed; no local OpenAI-compatible model server was available. |
| 2026-06-06T17:23Z | local GPU probe | `nvidia-smi` unavailable on this host. |
| 2026-06-06T17:30Z | repeated `sinfo` / `squeue` probes after wait | Both timed out after 20 seconds. |
| 2026-06-06T17:33Z | no-op `sbatch --wrap=hostname` probe | Timed out after 30 seconds before returning a job id. |

## Current Status

The blocker is no longer “cannot produce any patch on a real instance.” That milestone is cleared.

The current remaining gap is **verification**:
- the successful run produced a non-empty patch
- but the executor still does not run the official SWE-Bench verifier or targeted tests in the loop
- so the patch is a candidate patch, not yet a verified fix

## Next Smoke / Validation Direction

The next practical step is to keep the same successful ingredients:
- 1 GPU
- 1 worker (`Qwen/Qwen2.5-Coder-14B-Instruct`)
- targeted `INSTANCE_ID`
- role-shaped prompt budgeting

and add validation:
- apply the candidate patch in the materialized checkout
- run a focused reproduction/test step
- then, if available, run the official SWE-Bench harness/verifier
