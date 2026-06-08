# Codex-Suite Single Design

This folder contains the frozen orchestration design used by the
`codex_suite_100_vs_gpt55` study.

## Files

- `orchestration_design.json`: executable JSON design consumed by
  `vao.swebench_orchestration.executor`.
- `orchestration_design.annotated.jsonc`: commented mirror for humans. This is
  not consumed by the executor.

The design file is intentionally kept as strict JSON. Do not add inline comments
or `_comment` fields to it: the executor loads it with `json.loads`, and the
Pydantic schema forbids extra fields. Keep the `.jsonc` mirror in sync when the
executable design changes.

## Top-Level Fields

- `design_id`: stable identifier for this frozen design.
- `evidence_level`: protocol label for the design and downstream runs.
- `benchmark`: dataset and split targeted by the design.
- `assumptions`: constraints assumed during design, including anti-leakage rules.
- `mode_taxonomy`: issue categories used by the router.
- `optimization_loss`: objective the design tries to minimize.
- `logging_plan`: required trace and manifest logging behavior.
- `expected_tradeoffs`: known cost, complexity, and verifier tradeoffs.
- `orchestrations`: executable orchestration specs. This design contains one.

## Selected Orchestration

`codex_suite_single_self_optimizing_v1` is a hierarchical routed solver. It uses
public issue text and repository evidence first, then patch and verifier feedback.
Gold patches and private metadata are not allowed in runtime prompts.

## Components

- `codex_triage_router`: classifies the issue mode and proposes likely files or
  tests. It uses `codex_gpt_5_4_mini_router`.
- `codex_fast_localizer`: narrows the edit surface from router output and issue
  text. It uses `codex_gpt_5_3_codex_spark_fast`.
- `codex_primary_patcher`: produces the main minimal unified diff. It uses
  `codex_gpt_5_4_patcher`.
- `codex_verifier_reviewer`: reads patch, traces, local verifier output, and
  patch-apply failures to accept, reject, or request repair. It uses
  `codex_gpt_5_4_reviewer`.
- `codex_hard_case_fallback`: performs one final escalation for empty patches,
  malformed diffs, verifier-negative patches with actionable logs, or low router
  confidence. It uses `codex_gpt_5_5_planner`.

## Policies

- `routing_policy`: maps issue modes to cheap or escalated paths.
- `patch_policy`: caps patch attempts at two primary patches plus one fallback.
- `verification_policy`: evaluates non-empty patches with the local no-Docker
  verifier when possible.
- `fallback_policy`: defines when escalation is allowed.
- `stopping_rule`: stops on resolved verifier status, exhausted patch budget,
  non-actionable verifier incompatibility, or excessive uncertainty.
- `complexity`: records the design's agent count, routing branches, tool
  policies, prompt templates, patch budget, and context budget for loss analysis.
