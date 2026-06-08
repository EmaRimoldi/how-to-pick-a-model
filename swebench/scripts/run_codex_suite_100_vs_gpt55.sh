#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
cd "${REPO_ROOT}"

export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}/swebench/src:${REPO_ROOT}/swebench:${REPO_ROOT}"
export PATH="${HOME}/.nvm/versions/node/v24.14.1/bin:${PATH}"

DATASET_NAME="${DATASET_NAME:-princeton-nlp/SWE-Bench_Verified}"
SPLIT="${SPLIT:-test}"
MAX_INSTANCES="${MAX_INSTANCES:-100}"
SEED="${SEED:-20260605}"
STUDY_ROOT="${STUDY_ROOT:-swebench/studies/codex_suite_100_vs_gpt55}"
STUDY_ROOT="${STUDY_ROOT%/}"
DATA_DIR="${DATA_DIR:-${STUDY_ROOT}/data/verified_100}"
RUN_ID="${RUN_ID:-codex_suite_100_vs_gpt55_$(date +%Y%m%d_%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-${STUDY_ROOT}/runs/${RUN_ID}}"
EVAL_ROOT="${EVAL_ROOT:-${STUDY_ROOT}/evaluations/${RUN_ID}}"
CHECKOUT_ROOT="${CHECKOUT_ROOT:-${RUN_ROOT}/checkouts}"
VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-1800}"
LOCAL_PYTHON="${LOCAL_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
PARALLEL_WORKERS="${PARALLEL_WORKERS:-1}"
MAX_CALLS_PER_COMPONENT="${MAX_CALLS_PER_COMPONENT:-1}"
ORCH_CONFIG="${ORCH_CONFIG:-${STUDY_ROOT}/configs/swebench_orchestration_codex_suite_100.yaml}"
BASELINE_CONFIG="${BASELINE_CONFIG:-${STUDY_ROOT}/configs/swebench_orchestration_gpt55_baseline_100.yaml}"
ORCH_WORKERS_CONFIG="${ORCH_WORKERS_CONFIG:-${STUDY_ROOT}/configs/swebench_codex_suite_workers.yaml}"
BASELINE_WORKERS_CONFIG="${BASELINE_WORKERS_CONFIG:-${STUDY_ROOT}/configs/swebench_gpt55_baseline_worker.yaml}"
ORCH_DESIGN="${ORCH_DESIGN:-${STUDY_ROOT}/designs/codex_suite_single/orchestration_design.json}"
BASELINE_DESIGN="${BASELINE_DESIGN:-${STUDY_ROOT}/designs/gpt55_baseline/orchestration_design.json}"
LOSS_CONFIG="${LOSS_CONFIG:-${STUDY_ROOT}/loss_config.yaml}"
META_PROMPT_TEMPLATE="${META_PROMPT_TEMPLATE:-${STUDY_ROOT}/prompts/meta_designer_prompt_template.txt}"
RUNTIME_PROMPT_TEMPLATE="${RUNTIME_PROMPT_TEMPLATE:-${STUDY_ROOT}/prompts/runtime_component_prompt_template.md}"

PY="${REPO_ROOT}/.venv/bin/python"
mkdir -p "${RUN_ROOT}" "${CHECKOUT_ROOT}" "${DATA_DIR}" "${EVAL_ROOT}" \
  "${RUN_ROOT}/config_snapshot" "${RUN_ROOT}/prompt_snapshot"

cp -f "${ORCH_CONFIG}" "${RUN_ROOT}/config_snapshot/"
cp -f "${BASELINE_CONFIG}" "${RUN_ROOT}/config_snapshot/"
cp -f "${ORCH_WORKERS_CONFIG}" "${RUN_ROOT}/config_snapshot/"
cp -f "${BASELINE_WORKERS_CONFIG}" "${RUN_ROOT}/config_snapshot/"
cp -f "${ORCH_DESIGN}" "${RUN_ROOT}/config_snapshot/codex_suite_orchestration_design.json"
cp -f "${BASELINE_DESIGN}" "${RUN_ROOT}/config_snapshot/gpt55_baseline_orchestration_design.json"
cp -f "${LOSS_CONFIG}" "${RUN_ROOT}/loss_config.yaml"
cp -f "${META_PROMPT_TEMPLATE}" "${RUN_ROOT}/prompt_snapshot/"
cp -f "${RUNTIME_PROMPT_TEMPLATE}" "${RUN_ROOT}/prompt_snapshot/"

echo "started_at=$(date -Is)"
echo "host=$(hostname)"
echo "run_id=${RUN_ID}"
echo "study_root=${STUDY_ROOT}"
echo "run_root=${RUN_ROOT}"
echo "eval_root=${EVAL_ROOT}"
echo "data_dir=${DATA_DIR}"
echo "max_instances=${MAX_INSTANCES}"
echo "parallel_workers=${PARALLEL_WORKERS}"
echo "max_calls_per_component=${MAX_CALLS_PER_COMPONENT}"
echo "codex=$(command -v codex || true)"

cat > "${RUN_ROOT}/run_manifest.yaml" <<EOF
run_id: ${RUN_ID}
created_at: $(date -Is)
slurm_job_id: ${SLURM_JOB_ID:-none}
host: $(hostname)
study_root: ${STUDY_ROOT}
dataset_name: ${DATASET_NAME}
split: ${SPLIT}
max_instances: ${MAX_INSTANCES}
parallel_workers: ${PARALLEL_WORKERS}
max_calls_per_component: ${MAX_CALLS_PER_COMPONENT}
data_dir: ${DATA_DIR}
run_root: ${RUN_ROOT}
eval_root: ${EVAL_ROOT}
checkout_root: ${CHECKOUT_ROOT}
configs:
  orchestration_executor: ${ORCH_CONFIG}
  orchestration_workers: ${ORCH_WORKERS_CONFIG}
  baseline_executor: ${BASELINE_CONFIG}
  baseline_workers: ${BASELINE_WORKERS_CONFIG}
designs:
  orchestration: ${ORCH_DESIGN}
  baseline: ${BASELINE_DESIGN}
prompts:
  meta_designer_template: ${META_PROMPT_TEMPLATE}
  runtime_component_template: ${RUNTIME_PROMPT_TEMPLATE}
loss_config: ${LOSS_CONFIG}
outputs:
  orchestration_predictions: ${RUN_ROOT}/orchestration/executor/predictions.jsonl
  baseline_predictions: ${RUN_ROOT}/gpt55_baseline/executor/predictions.jsonl
  orchestration_evaluation: ${EVAL_ROOT}/orchestration_local_eval/evaluation_manifest.json
  baseline_evaluation: ${EVAL_ROOT}/gpt55_baseline_local_eval/evaluation_manifest.json
  comparison_summary: ${RUN_ROOT}/comparison_summary.json
EOF

if [[ ! -s "${DATA_DIR}/instances_public.jsonl" ]]; then
  "${PY}" -m vao.swebench_orchestration.download \
    --dataset-name "${DATASET_NAME}" \
    --split "${SPLIT}" \
    --limit "${MAX_INSTANCES}" \
    --seed "${SEED}" \
    --output-dir "${DATA_DIR}"
fi

"${PY}" -m vao.swebench_orchestration.executor \
  --config "${ORCH_CONFIG}" \
  --instances "${DATA_DIR}/instances_public.jsonl" \
  --output-dir "${RUN_ROOT}/orchestration/executor" \
  --run-id "${RUN_ID}_orchestration" \
  --max-instances "${MAX_INSTANCES}" \
  --parallel-workers "${PARALLEL_WORKERS}" \
  --max-calls-per-component "${MAX_CALLS_PER_COMPONENT}" \
  --materialize-checkouts \
  --checkout-root "${CHECKOUT_ROOT}/orchestration"

"${PY}" -m vao.swebench_orchestration.evaluate \
  --dataset-name "${DATASET_NAME}" \
  --split "${SPLIT}" \
  --predictions "${RUN_ROOT}/orchestration/executor/predictions.jsonl" \
  --run-id "${RUN_ID}_orchestration_local_eval" \
  --output-dir "${EVAL_ROOT}/orchestration_local_eval" \
  --backend local \
  --local-python "${LOCAL_PYTHON}" \
  --timeout "${VERIFY_TIMEOUT}" \
  --execute || true

"${PY}" -m vao.swebench_orchestration.executor \
  --config "${BASELINE_CONFIG}" \
  --instances "${DATA_DIR}/instances_public.jsonl" \
  --output-dir "${RUN_ROOT}/gpt55_baseline/executor" \
  --run-id "${RUN_ID}_gpt55_baseline" \
  --max-instances "${MAX_INSTANCES}" \
  --parallel-workers "${PARALLEL_WORKERS}" \
  --max-calls-per-component 1 \
  --materialize-checkouts \
  --checkout-root "${CHECKOUT_ROOT}/gpt55_baseline"

"${PY}" -m vao.swebench_orchestration.evaluate \
  --dataset-name "${DATASET_NAME}" \
  --split "${SPLIT}" \
  --predictions "${RUN_ROOT}/gpt55_baseline/executor/predictions.jsonl" \
  --run-id "${RUN_ID}_gpt55_baseline_local_eval" \
  --output-dir "${EVAL_ROOT}/gpt55_baseline_local_eval" \
  --backend local \
  --local-python "${LOCAL_PYTHON}" \
  --timeout "${VERIFY_TIMEOUT}" \
  --execute || true

"${PY}" - "${RUN_ROOT}" "${RUN_ID}" "${EVAL_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

run_root = Path(sys.argv[1])
run_id = sys.argv[2]
eval_root = Path(sys.argv[3])

def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def summarize(name: str, executor_rel: str, eval_rel: str) -> dict:
    executor_manifest = load(run_root / executor_rel / "executor_manifest.json")
    eval_manifest = load(eval_root / eval_rel / "evaluation_manifest.json")
    predictions_path = run_root / executor_rel / "predictions.jsonl"
    predictions = []
    if predictions_path.exists():
        predictions = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = eval_manifest.get("report") or {}
    instance_results = eval_manifest.get("instance_results") or []
    resolved = sum(1 for row in report.values() if isinstance(row, dict) and row.get("resolved") is True)
    patch_applied = sum(1 for row in report.values() if isinstance(row, dict) and row.get("patch_successfully_applied") is True)
    return {
        "name": name,
        "instances": len(predictions),
        "nonempty_patches": sum(1 for row in predictions if str(row.get("model_patch") or "").strip()),
        "empty_patches": sum(1 for row in predictions if not str(row.get("model_patch") or "").strip()),
        "resolved": resolved,
        "resolved_rate": resolved / len(predictions) if predictions else None,
        "patch_successfully_applied": patch_applied,
        "executor_manifest": str(run_root / executor_rel / "executor_manifest.json"),
        "evaluation_manifest": str(eval_root / eval_rel / "evaluation_manifest.json"),
        "returncode": eval_manifest.get("returncode"),
        "completed_instances": sum(1 for row in instance_results if row.get("report_exists")),
        "total_input_tokens": _sum_trace_tokens(run_root / executor_rel / "traces.jsonl", "input_tokens"),
        "total_output_tokens": _sum_trace_tokens(run_root / executor_rel / "traces.jsonl", "output_tokens"),
        "total_wall_seconds": _sum_trace_float(run_root / executor_rel / "traces.jsonl", "wall_seconds"),
    }

def _trace_rows(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def _sum_trace_tokens(path: Path, key: str) -> int:
    return int(sum(int(row.get(key) or 0) for row in _trace_rows(path)))

def _sum_trace_float(path: Path, key: str) -> float:
    return float(sum(float(row.get(key) or 0.0) for row in _trace_rows(path)))

summary = {
    "run_id": run_id,
    "orchestration": summarize("codex_suite_single_self_optimizing_v1", "orchestration/executor", "orchestration_local_eval"),
    "baseline": summarize("gpt-5.5 single-worker baseline", "gpt55_baseline/executor", "gpt55_baseline_local_eval"),
}
orch = summary["orchestration"]
base = summary["baseline"]
summary["comparison"] = {
    "resolved_delta_orchestration_minus_baseline": orch["resolved"] - base["resolved"],
    "resolved_rate_delta_orchestration_minus_baseline": (
        None if orch["resolved_rate"] is None or base["resolved_rate"] is None else orch["resolved_rate"] - base["resolved_rate"]
    ),
    "nonempty_patch_delta_orchestration_minus_baseline": orch["nonempty_patches"] - base["nonempty_patches"],
    "wall_seconds_delta_orchestration_minus_baseline": orch["total_wall_seconds"] - base["total_wall_seconds"],
}
out = run_root / "comparison_summary.json"
out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "finished_at=$(date -Is)"
echo "summary=${RUN_ROOT}/comparison_summary.json"
