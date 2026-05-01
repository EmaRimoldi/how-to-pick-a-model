#!/usr/bin/env bash
set -euo pipefail

TASK_FILE="${1:-.z_probe_families.txt}"
SEEDS="${2:-8101:5}"
OUTPUT_ROOT="${3:-runs/autoresearch_cifar10/z_probe_baselines}"
RUN_PREFIX="${4:-zprobe}"
MODEL="${5:-gpt_5_4_mini}"

if [[ -z "${SLURM_ARRAY_TASK_ID:-}" ]]; then
  echo "SLURM_ARRAY_TASK_ID is required" >&2
  exit 2
fi

mapfile -t TASKS < "$TASK_FILE"
FAMILY="${TASKS[$SLURM_ARRAY_TASK_ID]:-}"
if [[ -z "$FAMILY" ]]; then
  echo "No family for array index ${SLURM_ARRAY_TASK_ID}" >&2
  exit 3
fi

cd /home/erimoldi/openclaw_remote/projects/NeurIPS_2026
source .venv/bin/activate
export PYTHONPATH=src:.

python -m vao.analysis.autoresearch_cifar10_pilot \
  --config configs/autoresearch_cifar10_pilot.yaml \
  --models "$MODEL" \
  --families "$FAMILY" \
  --seeds "$SEEDS" \
  --steps 0 \
  --split pilot \
  --output-root "$OUTPUT_ROOT" \
  --run-prefix "$RUN_PREFIX"
