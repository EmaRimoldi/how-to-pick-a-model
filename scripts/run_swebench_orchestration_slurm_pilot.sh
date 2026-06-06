#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
cd "${REPO_ROOT}"

SWEBENCH_ROOT="${SWEBENCH_ROOT:-${REPO_ROOT}/swebench}"
SLURM_LOCAL_ROOT_DEFAULT="${SWEBENCH_ROOT}/runtime"
if [[ -n "${SLURM_TMPDIR:-}" ]]; then
  SLURM_LOCAL_ROOT_DEFAULT="${SLURM_TMPDIR}/swebench_runtime"
fi

CONFIG="${CONFIG:-configs/swebench_orchestration_slurm_pilot.yaml}"
WORKERS_CONFIG="${WORKERS_CONFIG:-configs/swebench_open_source_workers_slurm_pilot.yaml}"
DESIGN="${DESIGN:-}"
ORCHESTRATION_ID="${ORCHESTRATION_ID:-}"
MAX_INSTANCES="${MAX_INSTANCES:-4}"
PARALLEL_WORKERS="${PARALLEL_WORKERS:-2}"
MAX_CALLS_PER_COMPONENT="${MAX_CALLS_PER_COMPONENT:-1}"
RUN_ID="${RUN_ID:-swebench_orchestration_slurm_pilot_$(date +%Y%m%d_%H%M%S)}"
OUTPUT_DIR="${OUTPUT_DIR:-${SWEBENCH_ROOT}/runs/${RUN_ID}}"
LOG_DIR="${OUTPUT_DIR}/logs"
VLLM_VENV="${VLLM_VENV:-${SLURM_LOCAL_ROOT_DEFAULT}/.venv-vllm}"
PY311="${PY311:-$(command -v python3.11 || command -v python3 || true)}"
HF_HOME="${HF_HOME:-${SLURM_LOCAL_ROOT_DEFAULT}/.hf_cache}"
VLLM_START_TIMEOUT_SECONDS="${VLLM_START_TIMEOUT_SECONDS:-1800}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
VLLM_VERSION="${VLLM_VERSION:-0.10.2}"
TRANSFORMERS_SPEC="${TRANSFORMERS_SPEC:-transformers>=4.55,<5}"
TOKENIZERS_SPEC="${TOKENIZERS_SPEC:-tokenizers>=0.21,<0.22}"
HF_HUB_SPEC="${HF_HUB_SPEC:-huggingface_hub<1.0}"
NUMPY_SPEC="${NUMPY_SPEC:-numpy<2.3}"

if [[ -z "${DESIGN}" ]]; then
  echo "Set DESIGN=/path/to/orchestration_design.json before running this script." >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" "${HF_HOME}"
mkdir -p "${SWEBENCH_ROOT}" "${SLURM_LOCAL_ROOT_DEFAULT}"

export HF_HOME
export TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-${HF_HOME}/transformers}"
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}"

echo "started_at=$(date -Is)"
echo "host=$(hostname)"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
echo "design=${DESIGN}"
echo "orchestration_id=${ORCHESTRATION_ID:-<auto>}"
echo "swebench_root=${SWEBENCH_ROOT}"
echo "slurm_local_root=${SLURM_LOCAL_ROOT_DEFAULT}"
echo "output_dir=${OUTPUT_DIR}"
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi || true

if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  echo "Missing project venv at ${REPO_ROOT}/.venv" >&2
  exit 1
fi

if [[ -z "${PY311}" ]]; then
  echo "Could not find python3.11 or python3 for vLLM env creation" >&2
  exit 1
fi

if [[ ! -x "${VLLM_VENV}/bin/python" ]]; then
  "${PY311}" -m venv "${VLLM_VENV}"
fi

if ! "${VLLM_VENV}/bin/python" - "${VLLM_VERSION}" <<'PY' >/dev/null 2>&1
import importlib.metadata as md
import sys

required_vllm = sys.argv[1]
try:
    vllm_version = md.version("vllm")
    transformers_version = md.version("transformers")
except md.PackageNotFoundError:
    raise SystemExit(1)

if vllm_version != required_vllm:
    raise SystemExit(1)
if int(transformers_version.split(".", 1)[0]) >= 5:
    raise SystemExit(1)
PY
then
  "${VLLM_VENV}/bin/python" -m pip install -U pip setuptools wheel
  "${VLLM_VENV}/bin/python" -m pip install --upgrade --force-reinstall "vllm==${VLLM_VERSION}"
  "${VLLM_VENV}/bin/python" -m pip install --upgrade --force-reinstall "${TRANSFORMERS_SPEC}" "${TOKENIZERS_SPEC}" "${HF_HUB_SPEC}" "${NUMPY_SPEC}"
fi

"${VLLM_VENV}/bin/python" - <<'PY'
import importlib.metadata as md
print("vllm", md.version("vllm"))
print("transformers", md.version("transformers"))
print("tokenizers", md.version("tokenizers"))
print("huggingface_hub", md.version("huggingface_hub"))
print("numpy", md.version("numpy"))
PY

mapfile -t WORKER_ROWS < <("${REPO_ROOT}/.venv/bin/python" - "$DESIGN" "$WORKERS_CONFIG" "$ORCHESTRATION_ID" <<'PY'
import json
import sys
import urllib.parse
from pathlib import Path

import yaml

design = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
workers = (yaml.safe_load(Path(sys.argv[2]).read_text(encoding='utf-8')) or {}).get('workers', {})
requested_orch = sys.argv[3] or None
orchestrations = design.get('orchestrations', [])
if not orchestrations:
    raise SystemExit('No orchestrations found in design')
orch = orchestrations[0] if requested_orch is None else next((o for o in orchestrations if o.get('orchestration_id') == requested_orch), None)
if orch is None:
    raise SystemExit(f'Unknown orchestration_id: {requested_orch}')
seen = []
for component in orch.get('components', []):
    alias = component['model']
    if alias not in seen:
        seen.append(alias)
for alias in seen:
    if alias not in workers:
        raise SystemExit(f'Missing worker config for alias: {alias}')
    worker = workers[alias]
    port = urllib.parse.urlparse(worker['base_url']).port
    if port is None:
        raise SystemExit(f"Worker {alias} base_url lacks a port: {worker['base_url']}")
    print(f"{alias}\t{worker['model_id']}\t{port}")
PY
)

if [[ ${#WORKER_ROWS[@]} -eq 0 ]]; then
  echo "No worker aliases selected by the orchestration." >&2
  exit 1
fi

GPU_SOURCE="${CUDA_VISIBLE_DEVICES:-}"
if [[ -z "${GPU_SOURCE}" ]]; then
  GPU_SOURCE="$(nvidia-smi --query-gpu=index --format=csv,noheader | paste -sd, -)"
fi
IFS=',' read -r -a GPU_IDS <<< "${GPU_SOURCE}"
if (( ${#GPU_IDS[@]} < ${#WORKER_ROWS[@]} )); then
  echo "Need at least ${#WORKER_ROWS[@]} GPUs for selected worker aliases, got ${#GPU_IDS[@]} (${GPU_SOURCE})." >&2
  exit 1
fi

declare -a VLLM_PIDS=()
cleanup() {
  for pid in "${VLLM_PIDS[@]:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" || true
      wait "${pid}" || true
    fi
  done
}
trap cleanup EXIT

for index in "${!WORKER_ROWS[@]}"; do
  IFS=$'\t' read -r alias model_id port <<< "${WORKER_ROWS[$index]}"
  gpu_id="${GPU_IDS[$index]}"
  log_path="${LOG_DIR}/${alias}.vllm.log"
  echo "launch_worker alias=${alias} gpu=${gpu_id} port=${port} model=${model_id}"
  CUDA_VISIBLE_DEVICES="${gpu_id}" "${VLLM_VENV}/bin/vllm" serve "${model_id}" \
    --host 127.0.0.1 \
    --port "${port}" \
    --served-model-name "${model_id}" \
    --max-model-len "${MAX_MODEL_LEN}" \
    >"${log_path}" 2>&1 &
  VLLM_PIDS+=("$!")
done

deadline=$((SECONDS + VLLM_START_TIMEOUT_SECONDS))
for index in "${!WORKER_ROWS[@]}"; do
  IFS=$'\t' read -r alias _model_id port <<< "${WORKER_ROWS[$index]}"
  until "${VLLM_VENV}/bin/python" - <<PY >/dev/null 2>&1
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:${port}/v1/models', timeout=10) as response:
    payload = json.load(response)
assert 'data' in payload
PY
  do
    if (( SECONDS >= deadline )); then
      echo "Worker ${alias} on port ${port} did not become ready in time." >&2
      tail -n 120 "${LOG_DIR}/${alias}.vllm.log" >&2 || true
      exit 1
    fi
    sleep 10
  done
  echo "worker_ready alias=${alias} port=${port}"
done

EXEC_CMD=(
  "${REPO_ROOT}/.venv/bin/python" -m vao.swebench_orchestration.executor
  --config "${CONFIG}"
  --design "${DESIGN}"
  --workers-config "${WORKERS_CONFIG}"
  --output-dir "${OUTPUT_DIR}/executor"
  --run-id "${RUN_ID}"
  --max-instances "${MAX_INSTANCES}"
  --parallel-workers "${PARALLEL_WORKERS}"
  --max-calls-per-component "${MAX_CALLS_PER_COMPONENT}"
)
if [[ -n "${ORCHESTRATION_ID}" ]]; then
  EXEC_CMD+=(--orchestration-id "${ORCHESTRATION_ID}")
fi
"${EXEC_CMD[@]}"

echo "finished_at=$(date -Is)"
echo "run_id=${RUN_ID}"
echo "output_dir=${OUTPUT_DIR}"
echo "design=${DESIGN}"
