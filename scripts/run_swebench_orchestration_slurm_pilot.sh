#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
cd "${REPO_ROOT}"

SWEBENCH_ROOT="${SWEBENCH_ROOT:-${REPO_ROOT}/swebench}"
SLURM_LOCAL_ROOT_DEFAULT=""
if [[ -n "${SLURM_TMPDIR:-}" ]]; then
  SLURM_LOCAL_ROOT_DEFAULT="${SLURM_TMPDIR}/swebench_runtime"
elif [[ -n "${TMPDIR:-}" && -d "${TMPDIR}" && -w "${TMPDIR}" ]]; then
  SLURM_LOCAL_ROOT_DEFAULT="${TMPDIR}/swebench_runtime"
elif [[ -n "${SLURM_JOB_ID:-}" && -d /tmp && -w /tmp ]]; then
  SLURM_LOCAL_ROOT_DEFAULT="/tmp/${USER:-erimoldi}/swebench_runtime_${SLURM_JOB_ID}"
else
  SLURM_LOCAL_ROOT_DEFAULT="${SWEBENCH_ROOT}/runtime"
fi
SLURM_LOCAL_ROOT="${SLURM_LOCAL_ROOT:-${SLURM_LOCAL_ROOT_DEFAULT}}"

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
VLLM_VENV="${VLLM_VENV:-${SLURM_LOCAL_ROOT}/.venv-vllm}"
PY311="${PY311:-$(command -v python3.11 || command -v python3 || true)}"
HF_HOME="${HF_HOME:-${SLURM_LOCAL_ROOT}/.hf_cache}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-${HF_HOME}/hub}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-${SLURM_LOCAL_ROOT}/.cache}"
TORCHINDUCTOR_CACHE_DIR="${TORCHINDUCTOR_CACHE_DIR:-${SLURM_LOCAL_ROOT}/torchinductor_cache}"
TRITON_CACHE_DIR="${TRITON_CACHE_DIR:-${SLURM_LOCAL_ROOT}/triton_cache}"
VLLM_WORKER_MULTIPROC_METHOD="${VLLM_WORKER_MULTIPROC_METHOD:-spawn}"
HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-900}"
HF_HUB_ETAG_TIMEOUT="${HF_HUB_ETAG_TIMEOUT:-120}"
VLLM_START_TIMEOUT_SECONDS="${VLLM_START_TIMEOUT_SECONDS:-3600}"
VLLM_READY_POLL_SECONDS="${VLLM_READY_POLL_SECONDS:-10}"
PREFETCH_MODELS="${PREFETCH_MODELS:-1}"
MIN_LOCAL_SCRATCH_GB="${MIN_LOCAL_SCRATCH_GB:-80}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-16384}"
VLLM_VERSION="${VLLM_VERSION:-0.10.2}"
TRANSFORMERS_SPEC="${TRANSFORMERS_SPEC:-transformers>=4.55,<5}"
TOKENIZERS_SPEC="${TOKENIZERS_SPEC:-tokenizers>=0.21,<0.22}"
HF_HUB_SPEC="${HF_HUB_SPEC:-huggingface_hub<1.0}"
NUMPY_SPEC="${NUMPY_SPEC:-numpy<2.3}"

require_scratch_space() {
  if (( MIN_LOCAL_SCRATCH_GB <= 0 )); then
    return
  fi
  local available_kb required_kb
  available_kb="$(df -Pk "${SLURM_LOCAL_ROOT}" | awk 'NR == 2 {print $4}')"
  required_kb=$((MIN_LOCAL_SCRATCH_GB * 1024 * 1024))
  if [[ -n "${available_kb}" ]] && (( available_kb < required_kb )); then
    echo "Need at least ${MIN_LOCAL_SCRATCH_GB} GB free under ${SLURM_LOCAL_ROOT}; found $((available_kb / 1024 / 1024)) GB." >&2
    echo "Set SLURM_LOCAL_ROOT to a larger node-local scratch path or MIN_LOCAL_SCRATCH_GB=0 to bypass this guard." >&2
    exit 1
  fi
}

wait_for_worker() {
  local alias="$1"
  local port="$2"
  local pid="$3"
  local log_path="$4"
  local deadline=$((SECONDS + VLLM_START_TIMEOUT_SECONDS))
  local next_status=$((SECONDS + 60))

  until "${VLLM_VENV}/bin/python" - <<PY >/dev/null 2>&1
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:${port}/v1/models', timeout=10) as response:
    payload = json.load(response)
assert 'data' in payload
PY
  do
    if ! kill -0 "${pid}" 2>/dev/null; then
      local status=0
      wait "${pid}" || status=$?
      echo "Worker ${alias} on port ${port} exited before readiness with status ${status}." >&2
      tail -n 160 "${log_path}" >&2 || true
      exit 1
    fi
    if (( SECONDS >= deadline )); then
      echo "Worker ${alias} on port ${port} did not become ready in ${VLLM_START_TIMEOUT_SECONDS}s." >&2
      tail -n 160 "${log_path}" >&2 || true
      exit 1
    fi
    if (( SECONDS >= next_status )); then
      echo "waiting_worker alias=${alias} port=${port} elapsed=$((VLLM_START_TIMEOUT_SECONDS - (deadline - SECONDS)))s"
      next_status=$((SECONDS + 60))
    fi
    sleep "${VLLM_READY_POLL_SECONDS}"
  done
  echo "worker_ready alias=${alias} port=${port}"
}

if [[ -z "${DESIGN}" ]]; then
  echo "Set DESIGN=/path/to/orchestration_design.json before running this script." >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" "${HF_HOME}" "${TRANSFORMERS_CACHE}" "${XDG_CACHE_HOME}" "${TORCHINDUCTOR_CACHE_DIR}" "${TRITON_CACHE_DIR}"
mkdir -p "${SWEBENCH_ROOT}" "${SLURM_LOCAL_ROOT}"
require_scratch_space

export HF_HOME
export XDG_CACHE_HOME
export TRANSFORMERS_CACHE
export TORCHINDUCTOR_CACHE_DIR
export TRITON_CACHE_DIR
export VLLM_WORKER_MULTIPROC_METHOD
export HF_HUB_DOWNLOAD_TIMEOUT
export HF_HUB_ETAG_TIMEOUT
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}"

echo "started_at=$(date -Is)"
echo "host=$(hostname)"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
echo "design=${DESIGN}"
echo "orchestration_id=${ORCHESTRATION_ID:-<auto>}"
echo "swebench_root=${SWEBENCH_ROOT}"
echo "slurm_local_root=${SLURM_LOCAL_ROOT}"
echo "hf_home=${HF_HOME}"
echo "transformers_cache=${TRANSFORMERS_CACHE}"
echo "vllm_venv=${VLLM_VENV}"
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

if [[ "${PREFETCH_MODELS}" != "0" ]]; then
  prefetch_log="${LOG_DIR}/model_prefetch.log"
  echo "prefetch_models log=${prefetch_log}"
  if ! "${VLLM_VENV}/bin/python" - "${WORKER_ROWS[@]}" >"${prefetch_log}" 2>&1 <<'PY'
import sys
import time

from huggingface_hub import snapshot_download

seen = []
for row in sys.argv[1:]:
    alias, model_id, _port = row.split("\t")
    if model_id in seen:
        continue
    seen.append(model_id)
    print(f"prefetch_start alias={alias} model={model_id} at={time.strftime('%Y-%m-%dT%H:%M:%S%z')}", flush=True)
    path = snapshot_download(repo_id=model_id)
    print(f"prefetch_done alias={alias} model={model_id} path={path} at={time.strftime('%Y-%m-%dT%H:%M:%S%z')}", flush=True)
PY
  then
    echo "Model prefetch failed; tailing ${prefetch_log}" >&2
    tail -n 160 "${prefetch_log}" >&2 || true
    exit 1
  fi
  echo "prefetch_done log=${prefetch_log}"
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
    --download-dir "${TRANSFORMERS_CACHE}" \
    --max-model-len "${MAX_MODEL_LEN}" \
    >"${log_path}" 2>&1 &
  pid="$!"
  VLLM_PIDS+=("${pid}")
  wait_for_worker "${alias}" "${port}" "${pid}" "${log_path}"
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
