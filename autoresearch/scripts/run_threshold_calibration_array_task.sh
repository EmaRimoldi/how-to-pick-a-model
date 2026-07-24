#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="${1:-.threshold_calibration_tasks.tsv}"
SEED="${2:-7301}"
OUTPUT_ROOT="${3:-autoresearch/runs/threshold_calibration_pilot}"
RUN_PREFIX="${4:-deltasweep}"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
  echo "SLURM_ARRAY_TASK_ID is required" >&2
  exit 2
fi

mapfile -t TASKS < "$TASK_FILE"
TASK="${TASKS[$SLURM_ARRAY_TASK_ID]:-}"
if [[ -z "$TASK" ]]; then
  echo "No task for array index ${SLURM_ARRAY_TASK_ID}" >&2
  exit 3
fi

IFS=$'\t' read -r MODEL FAMILY <<< "$TASK"

cd "$PROJECT_ROOT"
source .venv/bin/activate
export PYTHONPATH=src:.

python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_pilot.yaml \
  --models "$MODEL" \
  --families "$FAMILY" \
  --seeds "$SEED" \
  --split pilot \
  --output-root "$OUTPUT_ROOT" \
  --run-prefix "$RUN_PREFIX"
