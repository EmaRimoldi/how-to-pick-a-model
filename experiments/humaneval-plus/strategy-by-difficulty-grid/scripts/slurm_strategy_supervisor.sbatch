#!/usr/bin/env bash
#SBATCH --job-name=toa-supervise
#SBATCH --partition=mit_normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00

set -euo pipefail

ROOT="${ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
RUN_ID="${RUN_ID:?Set RUN_ID}"
CONFIG_PATH="${CONFIG_PATH:?Set CONFIG_PATH}"
RUN_ROOT="${RUN_ROOT:-$ROOT/experiments/humaneval-plus/strategy-by-difficulty-grid/runs/$RUN_ID}"
NUM_SHARDS="${NUM_SHARDS:-8}"
ARRAY_LIMIT="${ARRAY_LIMIT:-1}"
GPU_PARTITION="${GPU_PARTITION:-ou_bcs_low}"
EXCLUDE_NODES="${EXCLUDE_NODES:-}"
RETRY="${RETRY:-0}"
MAX_RETRIES="${MAX_RETRIES:-2}"

cd "$ROOT"
source .venv/bin/activate

if python -m src.validate_strategy_run --config "$CONFIG_PATH" --run-id "$RUN_ID"; then
  python -m src.analyze_strategy_experiment --config "$CONFIG_PATH" --run-id "$RUN_ID"
  python -m src.analyze_strategy_router --config "$CONFIG_PATH" --run-id "$RUN_ID"
  python -m src.estimate_strategy_closure --config "$CONFIG_PATH" --run-id "$RUN_ID"
  python -m src.analyze_strategy_crossovers --config "$CONFIG_PATH" --run-id "$RUN_ID"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$RUN_ROOT/COMPLETE"
  echo "Run $RUN_ID is complete and analyzed."
  exit 0
fi

if (( RETRY >= MAX_RETRIES )); then
  date -u +%Y-%m-%dT%H:%M:%SZ > "$RUN_ROOT/SUPERVISOR_FAILED"
  echo "Run remains incomplete after $RETRY retries." >&2
  exit 1
fi

next_retry=$((RETRY + 1))
job_ids=()
for model in 1.5b 7b 32b; do
  SBATCH_ARGS=(
    --partition="$GPU_PARTITION"
    --array="0-$((NUM_SHARDS - 1))%${ARRAY_LIMIT}"
    --output="$RUN_ROOT/logs/retry${next_retry}-%x-%A_%a.out"
    --error="$RUN_ROOT/logs/retry${next_retry}-%x-%A_%a.err"
    --export=ALL
  )
  if [[ -n "$EXCLUDE_NODES" ]]; then
    SBATCH_ARGS+=(--exclude="$EXCLUDE_NODES")
  fi
  output="$({
    MODEL_KEY="$model" RUN_ID="$RUN_ID" NUM_SHARDS="$NUM_SHARDS" CONFIG_PATH="$CONFIG_PATH" \
      sbatch "${SBATCH_ARGS[@]}" \
        experiments/humaneval-plus/strategy-by-difficulty-grid/scripts/slurm_strategy_worker.sbatch
  })"
  job_ids+=("${output##* }")
done

dependency=$(IFS=:; echo "${job_ids[*]}")
RETRY="$next_retry" RUN_ID="$RUN_ID" CONFIG_PATH="$CONFIG_PATH" RUN_ROOT="$RUN_ROOT" \
  NUM_SHARDS="$NUM_SHARDS" ARRAY_LIMIT="$ARRAY_LIMIT" GPU_PARTITION="$GPU_PARTITION" \
  EXCLUDE_NODES="$EXCLUDE_NODES" \
  MAX_RETRIES="$MAX_RETRIES" \
  sbatch \
    --dependency="afterany:$dependency" \
    --output="$RUN_ROOT/logs/supervisor-retry${next_retry}-%j.out" \
    --error="$RUN_ROOT/logs/supervisor-retry${next_retry}-%j.err" \
    --export=ALL \
    experiments/humaneval-plus/strategy-by-difficulty-grid/scripts/slurm_strategy_supervisor.sbatch

echo "Submitted retry $next_retry workers: $dependency"
