#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
cd "${REPO_ROOT}"

PROJECT_PYTHON_DEFAULT="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "${PROJECT_PYTHON_DEFAULT}" && -x "/home/erimoldi/openclaw_remote/projects/NeurIPS_2026/.venv/bin/python" ]]; then
  PROJECT_PYTHON_DEFAULT="/home/erimoldi/openclaw_remote/projects/NeurIPS_2026/.venv/bin/python"
fi
PROJECT_PYTHON="${PROJECT_PYTHON:-${PROJECT_PYTHON_DEFAULT}}"
if [[ ! -x "${PROJECT_PYTHON}" ]]; then
  echo "Missing executable project Python at ${PROJECT_PYTHON}" >&2
  exit 1
fi

export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}"

BASE_CONFIG="${BASE_CONFIG:-swebench/runs/single50_updated_20260607_112356/meta_update_apply_local_v2/executor_config_updated.yaml}"
BASE_DESIGN="${BASE_DESIGN:-swebench/runs/single50_updated_20260607_112356/meta_update_apply_local_v2/orchestration_design_updated.json}"
WORKERS_CONFIG="${WORKERS_CONFIG:-configs/swebench_open_source_workers_slurm_pilot.yaml}"
ORCHESTRATION_ID="${ORCHESTRATION_ID:-swev_e250_routed_onepass_escalator_20260607_b4c1}"
INSTANCE_ID="${INSTANCE_ID:-sympy__sympy-16886}"
ROOT_RUN_ID="${ROOT_RUN_ID:-hierarchical_meta_loop_$(date -u +%Y%m%d_%H%M%S)}"
RUN_ROOT="${RUN_ROOT:-swebench/runs/${ROOT_RUN_ID}}"
EVAL_ROOT="${EVAL_ROOT:-swebench/evaluations/${ROOT_RUN_ID}}"
SLURM_PARTITION="${SLURM_PARTITION:-mit_preemptable}"
SLURM_GPUS="${SLURM_GPUS:-4}"
SLURM_CPUS="${SLURM_CPUS:-24}"
SLURM_MEM="${SLURM_MEM:-160G}"
SLURM_TIME="${SLURM_TIME:-04:00:00}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
PARALLEL_WORKERS="${PARALLEL_WORKERS:-1}"
MAX_CALLS_PER_COMPONENT="${MAX_CALLS_PER_COMPONENT:-1}"
EVAL_TIMEOUT="${EVAL_TIMEOUT:-1800}"
MODAL_MAX_WORKERS="${MODAL_MAX_WORKERS:-1}"
MIN_LOCAL_SCRATCH_GB="${MIN_LOCAL_SCRATCH_GB:-0}"

mkdir -p "${RUN_ROOT}" "${EVAL_ROOT}"

make_initial_config() {
  local output_config="$1"
  "${PROJECT_PYTHON}" - "$BASE_CONFIG" "$BASE_DESIGN" "$WORKERS_CONFIG" "$ORCHESTRATION_ID" "$output_config" <<'PY'
import sys
from pathlib import Path

import yaml

base_config, design, workers, orchestration_id, output_config = sys.argv[1:]
payload = yaml.safe_load(Path(base_config).read_text(encoding="utf-8")) or {}
executor = dict(payload.get("executor") or {})
executor["design"] = design
executor["workers_config"] = workers
executor["orchestration_id"] = orchestration_id
executor["public_literal_repair_enabled"] = False
executor["patch_repair_attempts"] = 1
payload["executor"] = executor
Path(output_config).write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
PY
}

wait_for_slurm_job() {
  local job_id="$1"
  local status_interval="${STATUS_INTERVAL_SECONDS:-30}"
  while squeue -h -j "${job_id}" >/tmp/swebench_meta_loop_squeue_${job_id}.txt 2>/tmp/swebench_meta_loop_squeue_${job_id}.err; do
    if [[ ! -s /tmp/swebench_meta_loop_squeue_${job_id}.txt ]]; then
      break
    fi
    echo "slurm_wait job_id=${job_id} $(tr -s ' ' ' ' </tmp/swebench_meta_loop_squeue_${job_id}.txt | sed 's/^ *//')"
    sleep "${status_interval}"
  done
  local state=""
  state="$(sacct -j "${job_id}" --format=JobID,State,ExitCode,Elapsed,NodeList -P -n 2>/dev/null | head -n 1 || true)"
  echo "slurm_done job_id=${job_id} sacct=${state:-unavailable}"
  if [[ -n "${state}" && "${state}" != *"|COMPLETED|"* ]]; then
    return 1
  fi
}

submit_executor_stage() {
  local stage_name="$1"
  local config_path="$2"
  local design_path="$3"
  local stage_run_id="${ROOT_RUN_ID}_${stage_name}"
  local stage_output_dir="${RUN_ROOT}/${stage_name}"
  local slurm_dir="${stage_output_dir}/slurm"
  mkdir -p "${slurm_dir}"
  local wrap_cmd
  wrap_cmd=$(
    printf '%q ' \
      env \
      REPO_ROOT="${REPO_ROOT}" \
      CONFIG="${config_path}" \
      DESIGN="${design_path}" \
      WORKERS_CONFIG="${WORKERS_CONFIG}" \
      ORCHESTRATION_ID="${ORCHESTRATION_ID}" \
      INSTANCE_ID="${INSTANCE_ID}" \
      RUN_ID="${stage_run_id}" \
      OUTPUT_DIR="${stage_output_dir}" \
      MAX_INSTANCES="${MAX_INSTANCES}" \
      PARALLEL_WORKERS="${PARALLEL_WORKERS}" \
      MAX_CALLS_PER_COMPONENT="${MAX_CALLS_PER_COMPONENT}" \
      MIN_LOCAL_SCRATCH_GB="${MIN_LOCAL_SCRATCH_GB}" \
      bash "${REPO_ROOT}/scripts/run_swebench_orchestration_slurm_pilot.sh"
  )
  local job_id
  job_id="$(sbatch \
    --parsable \
    --job-name="swebench-${stage_name}" \
    --partition="${SLURM_PARTITION}" \
    --gres="gpu:${SLURM_GPUS}" \
    --cpus-per-task="${SLURM_CPUS}" \
    --mem="${SLURM_MEM}" \
    --time="${SLURM_TIME}" \
    --output="${slurm_dir}/%j.out" \
    --error="${slurm_dir}/%j.err" \
    --wrap="cd ${REPO_ROOT@Q} && unset SLURM_TMPDIR && ${wrap_cmd}")"
  echo "${job_id}" >"${stage_output_dir}/slurm_job_id.txt"
  echo "submitted_stage stage=${stage_name} job_id=${job_id} output_dir=${stage_output_dir}"
  wait_for_slurm_job "${job_id}"
}

run_modal_eval() {
  local stage_name="$1"
  local stage_output_dir="$2"
  local eval_run_id="${ROOT_RUN_ID}_${stage_name}_modal_eval"
  local eval_output_dir="${EVAL_ROOT}/${stage_name}_modal_eval"
  "${PROJECT_PYTHON}" -m vao.swebench_orchestration.evaluate \
    --predictions "${stage_output_dir}/executor/predictions.jsonl" \
    --run-id "${eval_run_id}" \
    --output-dir "${eval_output_dir}" \
    --instance-ids "${INSTANCE_ID}" \
    --max-workers "${MODAL_MAX_WORKERS}" \
    --timeout "${EVAL_TIMEOUT}" \
    --modal \
    --execute
}

INITIAL_CONFIG="${RUN_ROOT}/initial_config.yaml"
make_initial_config "${INITIAL_CONFIG}"

echo "meta_loop_started root_run_id=${ROOT_RUN_ID}"
echo "run_root=${RUN_ROOT}"
echo "eval_root=${EVAL_ROOT}"
echo "instance_id=${INSTANCE_ID}"
echo "orchestration_id=${ORCHESTRATION_ID}"
echo "slurm_partition=${SLURM_PARTITION} slurm_gpus=${SLURM_GPUS}"

INITIAL_STAGE_DIR="${RUN_ROOT}/initial"
INITIAL_EVAL_DIR="${EVAL_ROOT}/initial_modal_eval"
submit_executor_stage initial "${INITIAL_CONFIG}" "${BASE_DESIGN}"
run_modal_eval initial "${INITIAL_STAGE_DIR}"

META_UPDATE_DIR="${RUN_ROOT}/meta_update"
UPDATED_DESIGN="${META_UPDATE_DIR}/orchestration_design_updated.json"
UPDATED_CONFIG="${META_UPDATE_DIR}/updated_config.yaml"
"${PROJECT_PYTHON}" -m vao.swebench_orchestration.meta_update \
  --config "${BASE_CONFIG}" \
  --design "${BASE_DESIGN}" \
  --orchestration-id "${ORCHESTRATION_ID}" \
  --executor-dir "${INITIAL_STAGE_DIR}/executor" \
  --evaluation-manifest "${INITIAL_EVAL_DIR}/evaluation_manifest.json" \
  --output-dir "${META_UPDATE_DIR}" \
  --updated-design-out "${UPDATED_DESIGN}" \
  --updated-config-out "${UPDATED_CONFIG}" \
  --invoke-codex

UPDATED_STAGE_DIR="${RUN_ROOT}/updated"
UPDATED_EVAL_DIR="${EVAL_ROOT}/updated_modal_eval"
submit_executor_stage updated "${UPDATED_CONFIG}" "${UPDATED_DESIGN}"
run_modal_eval updated "${UPDATED_STAGE_DIR}"

"${PROJECT_PYTHON}" - "${RUN_ROOT}/loop_summary.json" "${INITIAL_STAGE_DIR}" "${INITIAL_EVAL_DIR}" "${META_UPDATE_DIR}" "${UPDATED_STAGE_DIR}" "${UPDATED_EVAL_DIR}" <<'PY'
import json
import sys
from pathlib import Path

summary_path, initial_stage, initial_eval, meta_update, updated_stage, updated_eval = map(Path, sys.argv[1:])
payload = {
    "initial_stage_dir": str(initial_stage),
    "initial_eval_dir": str(initial_eval),
    "meta_update_dir": str(meta_update),
    "updated_stage_dir": str(updated_stage),
    "updated_eval_dir": str(updated_eval),
}
for key in ("initial_eval_dir", "updated_eval_dir"):
    manifest = Path(payload[key]) / "evaluation_manifest.json"
    if manifest.exists():
        manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
        report = manifest_payload.get("report") or {}
        validation = manifest_payload.get("prediction_validation") or {}
        payload[key.replace("_dir", "_report")] = {
            name: report.get(name)
            for name in (
                "submitted_instances",
                "completed_instances",
                "resolved_instances",
                "unresolved_instances",
                "error_instances",
                "empty_patch_instances",
            )
        }
        payload[key.replace("_dir", "_prediction_validation")] = {
            name: validation.get(name)
            for name in (
                "rows",
                "nonempty_patch_count",
                "empty_patch_ids",
                "patch_chars_min",
                "patch_chars_max",
                "model_names",
            )
        }
summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY

echo "meta_loop_finished summary=${RUN_ROOT}/loop_summary.json"
