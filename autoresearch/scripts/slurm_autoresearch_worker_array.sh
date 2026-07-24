#!/usr/bin/env bash
#SBATCH --job-name=ar-cifar10
#SBATCH --partition=mit_normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=autoresearch/artifacts/slurm/ar-cifar10-%A_%a.out
#SBATCH --error=autoresearch/artifacts/slurm/ar-cifar10-%A_%a.err

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TASK_MANIFEST="${TASK_MANIFEST:-${REPO_ROOT}/autoresearch/artifacts/slurm/campaign_pilot_tasks.tsv}"
CONFIG_PATH="${CONFIG_PATH:-autoresearch/configs/autoresearch_cifar10_model_routing.yaml}"
OUTPUT_ROOT="${OUTPUT_ROOT:-autoresearch/runs/slurm_pilot}"
RUN_PREFIX="${RUN_PREFIX:-slurm_pilot}"
AUTORESEARCH_HORIZON="${AUTORESEARCH_HORIZON:-20}"
AUTOSEARCH_MAX_STEPS="${AUTOSEARCH_MAX_STEPS:-256}"
THREADS="${SLURM_CPUS_PER_TASK:-8}"

export OMP_NUM_THREADS="${THREADS}"
export MKL_NUM_THREADS="${THREADS}"
export OPENBLAS_NUM_THREADS="${THREADS}"
export NUMEXPR_NUM_THREADS="${THREADS}"
export TORCH_NUM_THREADS="${THREADS}"
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}"

cd "${REPO_ROOT}"
mkdir -p autoresearch/artifacts/slurm "${OUTPUT_ROOT}"

if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
  echo "SLURM_ARRAY_TASK_ID is required" >&2
  exit 2
fi
if [[ ! -f "${TASK_MANIFEST}" ]]; then
  echo "TASK_MANIFEST not found: ${TASK_MANIFEST}" >&2
  exit 2
fi

LINE="$(awk -F'\t' -v idx="${SLURM_ARRAY_TASK_ID}" 'NR > 1 && $1 == idx {print; exit}' "${TASK_MANIFEST}")"
if [[ -z "${LINE}" ]]; then
  echo "No manifest row for task id ${SLURM_ARRAY_TASK_ID}" >&2
  exit 2
fi

IFS=$'\t' read -r TASK_ID MODE WORKER SEED SPLIT <<< "${LINE}"

echo "started_at=$(date -Is)"
echo "host=$(hostname)"
echo "task_id=${TASK_ID}"
echo "mode=${MODE}"
echo "worker=${WORKER}"
echo "seed=${SEED}"
echo "split=${SPLIT}"
echo "config=${CONFIG_PATH}"
echo "output_root=${OUTPUT_ROOT}"
echo "horizon=${AUTORESEARCH_HORIZON}"
echo "max_train_steps=${AUTOSEARCH_MAX_STEPS}"
echo "threads=${THREADS}"
command -v codex || true
codex --version || true

"${REPO_ROOT}/.venv/bin/python" -m autoresearch.analysis.autoresearch_cifar10_single_trajectory_campaign \
  --config "${CONFIG_PATH}" \
  --models "${WORKER}" \
  --workloads "${MODE}" \
  --seeds "${SEED}" \
  --split "${SPLIT}" \
  --steps "${AUTORESEARCH_HORIZON}" \
  --max-train-steps "${AUTOSEARCH_MAX_STEPS}" \
  --output-root "${OUTPUT_ROOT}" \
  --run-prefix "${RUN_PREFIX}"

echo "finished_at=$(date -Is)"
