# Hierarchical Meta-Orchestrator Loop Report

Last updated: 2026-06-07 02:08 UTC

## Executive summary

Abbiamo lanciato un esperimento piu completo della pipeline SWE-bench con una sola orchestrazione attiva:

- orchestration: `hierarchical_h1_distribution_router`
- instance: `sympy__sympy-16886`
- verifier: official SWE-bench harness via Modal
- active worker family: open-source Qwen workers served through vLLM on Slurm
- meta-orchestrator: Codex CLI model configured in `configs/swebench_orchestration_slurm_pilot.yaml`

Il loop finale ha raggiunto una patch verificata:

- `resolved_instances: 1`
- `unresolved_instances: 0`
- `error_instances: 0`
- `empty_patch_instances: 0`

La cosa importante e che il successo finale non e stato inserito manualmente come post-processing: il meta-orchestrator, dopo un failure bundle arricchito con trace notes e repo context pubblico, ha deciso di abilitare `public_literal_repair` dentro la sola policy hierarchical.

## Code changes made for this experiment

### 1. Meta-update module

Added:

- `src/vao/swebench_orchestration/meta_update.py`

This module builds a failure bundle from:

- executor manifest
- predictions
- traces
- official evaluation manifest
- selected trace events
- repo context artifacts

It then asks the meta-orchestrator to produce:

- `meta_update.json`
- an updated hierarchical `OrchestrationSpec`
- an `executor_config_patch`
- a materialized updated design JSON
- an updated executor config YAML

### 2. Design-gated deterministic repair

Updated:

- `src/vao/swebench_orchestration/executor.py`

`public_literal_repair` is now a capability, not an always-on fallback. The executor only runs it when both are true:

- executor config has `public_literal_repair_enabled: true`
- the active hierarchical design explicitly names `public_literal_repair` or an equivalent public-literal repair policy

This makes the repair a decision made by the meta-orchestrator policy.

### 3. Full-loop launcher

Added:

- `scripts/run_swebench_hierarchical_meta_loop.sh`

It runs:

1. initial hierarchical executor run
2. official Modal evaluation
3. meta-update
4. updated hierarchical executor run
5. official Modal evaluation

The actual successful v2 rerun reused the completed initial stage and reran the meta-update after improving the failure bundle.

### 4. Tests

Updated:

- `tests/test_swebench_orchestration.py`

Verification:

```bash
PYTHONPATH=src:. /home/erimoldi/openclaw_remote/projects/NeurIPS_2026/.venv/bin/python -m pytest -q tests/test_swebench_orchestration.py
```

Result:

```text
22 passed in 0.77s
```

`git diff --check` is clean.

## Run timeline

Root run:

- `swebench/runs/hierarchical_meta_loop_20260607_013249`

### Stage A: initial hierarchical run

Slurm:

- job: `15552386`
- partition: `mit_preemptable`
- node: `node4305`
- state: `COMPLETED`
- exit: `0:0`
- elapsed: `00:06:42`

Executor:

- run id: `hierarchical_meta_loop_20260607_013249_initial`
- config: `public_literal_repair_enabled: false`
- prediction: non-empty patch, 438 chars
- selected model: `Qwen/Qwen2.5-Coder-14B-Instruct`
- local apply check: passed

Official Modal result:

- eval: `swebench/evaluations/hierarchical_meta_loop_20260607_013249/initial_modal_eval`
- `resolved_instances: 0`
- `unresolved_instances: 1`
- `error_instances: 0`
- `empty_patch_instances: 0`

Interpretation: the initial hierarchical policy produced an applicable patch, but it was semantically wrong and did not resolve the official SWE-bench instance.

### Stage B: first meta-update

Artifacts:

- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update/meta_update.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update/orchestration_design_updated.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update/updated_config.yaml`

Meta-orchestrator decision:

- keep `public_literal_repair_enabled: false`
- increase `max_calls_per_component` to 2
- treat the failure as a semantic/SymPy localization problem

This was a useful negative result. The meta-update prompt had been too lossy: it included failure counters and selected patch/apply data, but not enough task-level evidence from router notes and repo snippets. Therefore the meta-orchestrator did not see that this was a public literal replacement case.

### Stage C: first updated run

Slurm:

- job: `15552679`
- partition: `mit_preemptable`
- node: `node4305`
- state: `COMPLETED`
- exit: `0:0`
- elapsed: `00:07:13`

Executor:

- run id: `hierarchical_meta_loop_20260607_013249_updated`
- config: `public_literal_repair_enabled: false`
- prediction: empty
- invalid patch count: 2

Official Modal wrapper:

- eval: `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_modal_eval`
- prediction validation: `empty_patch_ids: ["sympy__sympy-16886"]`
- stdout: `No instances to run.`

Interpretation: the model now tried the right conceptual fix, but kept emitting non-applicable hunks. Since the first meta-update had kept deterministic repair disabled, the executor correctly rejected the invalid model patches and emitted no candidate.

### Stage D: improved failure bundle and second meta-update

Code improvement:

- `meta_update.py` now includes:
  - `instances_path` when available
  - selected trace events with `payload_summary`
  - repo context snippets from `repo_context_path`

Artifacts:

- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/meta_update.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/orchestration_design_updated.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/updated_config.yaml`

Meta-orchestrator decision:

```json
{
  "public_literal_repair_enabled": true,
  "patch_repair_attempts": 2,
  "max_calls_per_component": 1
}
```

Key diagnosis from the meta-orchestrator:

- route was correct and high-confidence for a public literal Morse-code mapping issue
- primary specialist returned `patch_field_null`
- 14B fallback wasted budget on a deterministic one-token public literal edit
- design disabled `public_literal_repair` even though the failure class matched that primitive

### Stage E: updated v2 run

Slurm:

- job: `15552860`
- partition: `mit_preemptable`
- node: `node4305`
- state: `COMPLETED`
- exit: `0:0`
- elapsed: `00:07:14`

Executor:

- run id: `hierarchical_meta_loop_20260607_013249_updated_context_v2`
- config: `public_literal_repair_enabled: true`
- design explicitly names `public_literal_repair`
- model patch attempts: still non-applicable
- deterministic repair trace: `executor_public_literal_repair`
- local apply check for deterministic repair: passed
- prediction model label: `hierarchical_h1_distribution_router:public_literal_repair`

Generated patch:

```diff
diff --git a/sympy/crypto/crypto.py b/sympy/crypto/crypto.py
--- a/sympy/crypto/crypto.py
+++ b/sympy/crypto/crypto.py
@@ -1520,7 +1520,7 @@
     "..-": "U", "...-": "V",
     ".--": "W", "-..-": "X",
     "-.--": "Y", "--..": "Z",
-    "-----": "0", "----": "1",
+    "-----": "0", ".----": "1",
     "..---": "2", "...--": "3",
     "....-": "4", ".....": "5",
     "-....": "6", "--...": "7",
```

Official Modal result:

- eval: `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_context_v2_modal_eval`
- `submitted_instances: 1`
- `completed_instances: 1`
- `resolved_instances: 1`
- `unresolved_instances: 0`
- `error_instances: 0`
- `empty_patch_instances: 0`
- per-instance `resolved: true`
- `patch_apply_failed: false`

## Main conclusion

This is the first successful complete hierarchical meta-loop:

1. Run hierarchical orchestration.
2. Observe official verifier failure.
3. Let the meta-orchestrator update the hierarchical policy from failure evidence.
4. Rerun only the hierarchical orchestration.
5. Verify the updated policy with the official SWE-bench Modal harness.

The most important lesson is about information loss in the meta-update prompt. The first meta-update failed because the failure bundle was too compressed. Once the bundle included trace notes and public repo context, the meta-orchestrator correctly selected a deterministic repair primitive and the official verifier resolved the instance.

## Artifact index

Executor runs:

- `swebench/runs/hierarchical_meta_loop_20260607_013249/initial/executor/traces.jsonl`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/initial/executor/predictions.jsonl`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/updated/executor/traces.jsonl`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/updated/executor/predictions.jsonl`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/updated_context_v2/executor/traces.jsonl`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/updated_context_v2/executor/predictions.jsonl`

Meta-updates:

- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update/meta_update.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/meta_update.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/failure_bundle.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/orchestration_design_updated.json`
- `swebench/runs/hierarchical_meta_loop_20260607_013249/meta_update_context_v2/updated_config.yaml`

Official evaluations:

- `swebench/evaluations/hierarchical_meta_loop_20260607_013249/initial_modal_eval/evaluation_manifest.json`
- `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_modal_eval/evaluation_manifest.json`
- `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_context_v2_modal_eval/evaluation_manifest.json`
- `swebench/evaluations/hierarchical_meta_loop_20260607_013249/updated_context_v2_modal_eval/hierarchical_h1_distribution_router:public_literal_repair.hierarchical_meta_loop_20260607_013249_updated_context_v2_modal_eval.json`

Aggregated analysis:

- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/failure_summary.json`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/failure_report.md`
- `swebench/analysis/real_failure_modes_20260606/hierarchical_meta_loop_20260607/*.png`
