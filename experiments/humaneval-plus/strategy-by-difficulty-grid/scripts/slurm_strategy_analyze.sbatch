#!/usr/bin/env bash
#SBATCH --job-name=toa-analyze
#SBATCH --partition=mit_normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=2:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail
ROOT="${ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
CONFIG_PATH="${CONFIG_PATH:-experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml}"
cd "$ROOT"
mkdir -p logs
source .venv/bin/activate
ANALYZE_ARGS=(--config "$CONFIG_PATH")
if [[ -n "${RUN_ID:-}" ]]; then
  ANALYZE_ARGS+=(--run-id "$RUN_ID")
fi
python -m src.analyze_strategy_experiment "${ANALYZE_ARGS[@]}"
RAW_DIR=$(python -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1]))["paths"]["raw"])' "$CONFIG_PATH")
if compgen -G "$RAW_DIR/router_*.jsonl" >/dev/null; then
  python -m src.analyze_strategy_router "${ANALYZE_ARGS[@]}"
fi
python -m src.validate_strategy_run "${ANALYZE_ARGS[@]}"
