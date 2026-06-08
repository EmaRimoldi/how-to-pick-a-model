# SWE-bench Real-Instance Failure Analysis

## Runs

| run | traces | predictions | orchestration | instances_path |
|---|---:|---:|---|---|
| initial | 7 | 1 | hierarchical_h1_distribution_router | /tmp/swebench_runtime/target_instances/hierarchical_meta_loop_20260607_013249_initial/instances_sympy__sympy-16886.jsonl |
| updated | 8 | 1 | hierarchical_h1_distribution_router | /tmp/swebench_runtime/target_instances/hierarchical_meta_loop_20260607_013249_updated/instances_sympy__sympy-16886.jsonl |
| updated_context_v2 | 10 | 1 | hierarchical_h1_distribution_router | /tmp/swebench_runtime/target_instances/hierarchical_meta_loop_20260607_013249_updated_context_v2/instances_sympy__sympy-16886.jsonl |

## Patch Outcomes

Non-empty predictions: 2 / 3

| instance | model | patch chars | non-empty |
|---|---|---:|---|
| sympy__sympy-16886 | Qwen/Qwen2.5-Coder-14B-Instruct | 438 | True |
| sympy__sympy-16886 | hierarchical_h1_distribution_router | 0 | False |
| sympy__sympy-16886 | hierarchical_h1_distribution_router:public_literal_repair | 396 | True |

## Patch Empty Reasons

| class | count |
|---|---:|
| patch_field_null | 3 |

## Error Classes

| class | count |
|---|---:|
| none | 17 |
| patch_apply_check_failed:error:_patch_failed:_sympy_crypto_crypto.py:1522_error: | 5 |
| verifier_not_run | 3 |

## Phase Outcomes

| class | count |
|---|---:|
| fallback:error | 5 |
| localize:ok | 3 |
| observe:ok | 3 |
| other:ok | 3 |
| patch:ok | 3 |
| review:ok | 3 |
| verify:error | 3 |
| fallback:ok | 2 |

## Prompt Budgets

| run | instance | step | agent | level | estimated/actual input | requested | effective | context |
|---|---|---:|---|---|---:|---:|---:|---:|
| initial | sympy__sympy-16886 | 2 | h1_router | observe_role_shaped | 5992 | 2048 | 2048 | 16384 |
| initial | sympy__sympy-16886 | 3 | h1_budget_guard | observe_role_shaped | 6251 | 2048 | 2048 | 16384 |
| initial | sympy__sympy-16886 | 4 | h1_specialist_executor | patch_role_shaped | 7420 | 12000 | 8452 | 16384 |
| initial | sympy__sympy-16886 | 5 | h1_reviewer | observe_role_shaped | 6730 | 2048 | 2048 | 16384 |
| initial | sympy__sympy-16886 | 6 | h1_escalation_patcher | patch_role_shaped | 7898 | 16000 | 7974 | 16384 |
| updated | sympy__sympy-16886 | 2 | h1_router | observe_role_shaped | 6378 | 2048 | 2048 | 16384 |
| updated | sympy__sympy-16886 | 3 | h1_budget_guard | observe_role_shaped | 6645 | 2048 | 2048 | 16384 |
| updated | sympy__sympy-16886 | 4 | h1_specialist_executor | patch_role_shaped | 7889 | 12000 | 7983 | 16384 |
| updated | sympy__sympy-16886 | 5 | h1_reviewer | observe_role_shaped | 7143 | 2048 | 2048 | 16384 |
| updated | sympy__sympy-16886 | 6 | h1_escalation_patcher | patch_role_shaped | 8296 | 16000 | 7576 | 16384 |
| updated | sympy__sympy-16886 | 7 | h1_escalation_patcher | patch_role_shaped | 8212 | 16000 | 7660 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 2 | h1_router | observe_role_shaped | 6288 | 2048 | 2048 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 3 | h1_budget_guard | observe_role_shaped | 6575 | 2048 | 2048 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 4 | h1_specialist_executor | patch_role_shaped | 7803 | 12000 | 8069 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 5 | h1_reviewer | observe_role_shaped | 7131 | 2048 | 2048 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 6 | h1_escalation_patcher | patch_role_shaped | 8313 | 16000 | 7559 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 7 | h1_escalation_patcher | patch_role_shaped | 8203 | 16000 | 7669 | 16384 |
| updated_context_v2 | sympy__sympy-16886 | 8 | h1_escalation_patcher | patch_role_shaped | 8112 | 16000 | 7760 | 16384 |

## Repository Context

| run | instance | status | candidate files | snippets | snippet chars | search hits | tree entries |
|---|---|---|---:|---:|---:|---:|---:|
| initial | sympy__sympy-16886 | ready | 8 | 5 | 18000 | 28 | 160 |
| updated | sympy__sympy-16886 | ready | 8 | 5 | 18000 | 28 | 160 |
| updated_context_v2 | sympy__sympy-16886 | ready | 8 | 5 | 18000 | 28 | 160 |

## Plots

- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/patch_empty_reason_counts.png`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/error_class_counts.png`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/phase_outcomes.png`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/prompt_context_budget.png`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/repo_context_counts.png`
