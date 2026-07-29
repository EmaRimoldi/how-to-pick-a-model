#!/usr/bin/env bash
#SBATCH --job-name=toa-router-select
#SBATCH --partition=mit_normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00

set -euo pipefail

ROOT="${ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
WORKER_RUN_ID="${WORKER_RUN_ID:?Set WORKER_RUN_ID}"
WORKER_CONFIG="${WORKER_CONFIG:?Set WORKER_CONFIG}"
SEARCH_DIR="${SEARCH_DIR:?Set SEARCH_DIR}"
PHASE="${PHASE:-validation}"

cd "$ROOT"
source .venv/bin/activate
python -m src.evaluate_router_search \
  --config "$WORKER_CONFIG" \
  --worker-run-id "$WORKER_RUN_ID" \
  --search-dir "$SEARCH_DIR" \
  --phase "$PHASE"
if [[ "$PHASE" == "validation" ]]; then
  date -u +%Y-%m-%dT%H:%M:%SZ > "$SEARCH_DIR/VALIDATION_SELECTED"
else
  date -u +%Y-%m-%dT%H:%M:%SZ > "$SEARCH_DIR/TEST_EVALUATED"
fi
