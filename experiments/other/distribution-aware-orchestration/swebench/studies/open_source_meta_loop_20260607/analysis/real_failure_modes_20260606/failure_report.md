# SWE-bench Real-Instance Failure Analysis

## Runs

| run | traces | predictions | orchestration | instances_path |
|---|---:|---:|---|---|
| swebench_real_patch_15537314 | 7 | 1 | universal_u14_minimal_loop | experiments/swebench_orchestration/data/smoke/instances_public.jsonl |

## Patch Outcomes

Non-empty predictions: 0 / 1

| instance | model | patch chars | non-empty |
|---|---|---:|---|
| astropy__astropy-7671 | universal_u14_minimal_loop | 0 | False |

## Patch Empty Reasons

| class | count |
|---|---:|
| worker_error | 3 |

## Error Classes

| class | count |
|---|---:|
| context_budget_exceeded | 3 |
| none | 3 |
| verifier_not_run | 1 |

## Phase Outcomes

| class | count |
|---|---:|
| patch:error | 3 |
| observe:ok | 1 |
| review:ok | 1 |
| verify:error | 1 |
| verify:ok | 1 |

## Prompt Budgets

| run | instance | step | agent | level | estimated/actual input | requested | effective | context |
|---|---|---:|---|---|---:|---:|---:|---:|
| swebench_real_patch_15537314 | astropy__astropy-7671 | 2 | u_localize_patch | http_error_parsed | 11459 | 12000 | 0 | 16384 |
| swebench_real_patch_15537314 | astropy__astropy-7671 | 3 | u_localize_patch | http_error_parsed | 11459 | 12000 | 0 | 16384 |
| swebench_real_patch_15537314 | astropy__astropy-7671 | 4 | u_localize_patch | http_error_parsed | 11459 | 12000 | 0 | 16384 |

## Repository Context

| run | instance | status | candidate files | snippets | snippet chars | search hits | tree entries |
|---|---|---|---:|---:|---:|---:|---:|
| swebench_real_patch_15537314 | astropy__astropy-7671 | ready | 8 | 5 | 18000 | 28 | 160 |

## Plots

- `swebench/analysis/real_failure_modes_20260606/patch_empty_reason_counts.png`
- `swebench/analysis/real_failure_modes_20260606/error_class_counts.png`
- `swebench/analysis/real_failure_modes_20260606/phase_outcomes.png`
- `swebench/analysis/real_failure_modes_20260606/prompt_context_budget.png`
- `swebench/analysis/real_failure_modes_20260606/repo_context_counts.png`
