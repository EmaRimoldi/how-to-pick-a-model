#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

PY=".venv/bin/python"
RUN_ID="${RUN_ID:-full_$(date -u +%Y%m%dT%H%M%SZ)}"
LOG_FILE="experiments/humaneval-plus/qwen-model-size-frontier/data/raw/full_run_${RUN_ID}.log"

N_MODELS=3
N_PROBLEMS=164
MAX_ATTEMPTS=10
EXPECTED_TOKENS_PER_ATTEMPT="${EXPECTED_TOKENS_PER_ATTEMPT:-350}"
TOKENS_PER_SECOND="${TOKENS_PER_SECOND:-35}"

EXPECTED_TOKENS=$((N_MODELS * N_PROBLEMS * MAX_ATTEMPTS * EXPECTED_TOKENS_PER_ATTEMPT))
ETA_SECONDS=$((EXPECTED_TOKENS / TOKENS_PER_SECOND))
ETA_HOURS=$((ETA_SECONDS / 3600))
ETA_MINUTES=$(((ETA_SECONDS % 3600) / 60))

mkdir -p experiments/humaneval-plus/qwen-model-size-frontier/data/raw

echo "Run id: $RUN_ID"
echo "Rough ETA: ${ETA_HOURS}h ${ETA_MINUTES}m (${EXPECTED_TOKENS} generated tokens at ${TOKENS_PER_SECOND} tok/s)"
echo "Logging to $LOG_FILE"

{
  "$PY" -m vao.humaneval.run_eval --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml --run-id "$RUN_ID"
  "$PY" -m vao.humaneval.estimate --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml --run-id "$RUN_ID"
  "$PY" -m vao.humaneval.plot --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
} 2>&1 | tee "$LOG_FILE"
