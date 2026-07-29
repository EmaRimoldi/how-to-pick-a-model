#!/usr/bin/env bash
#SBATCH --job-name=toa-strategy
#SBATCH --partition=ou_bcs_low
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
MODEL_KEY="${MODEL_KEY:?Set MODEL_KEY to 1.5b, 7b, or 32b}"
RUN_ID="${RUN_ID:?Set RUN_ID}"
CONFIG_PATH="${CONFIG_PATH:-experiments/humaneval-plus/strategy-by-difficulty-grid/configs/strategy_experiment.yaml}"
EXTRA_ARGS=${EXTRA_ARGS:-}

cd "$ROOT"
mkdir -p logs
module load cuda/12.9.1
export HF_HOME="${HF_HOME:-/orcd/data/tpoggio/001/erimoldi/huggingface}"
export TRANSFORMERS_CACHE="$HF_HOME/hub"
export SSL_CERT_FILE=/etc/pki/tls/certs/ca-bundle.crt
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
export PYTORCH_ALLOC_CONF=expandable_segments:True

source .venv/bin/activate
nvidia-smi
ARGS=(
  --config "$CONFIG_PATH"
  --model-key "$MODEL_KEY"
  --run-id "$RUN_ID"
)
if [[ -n "${NUM_SHARDS:-}" ]]; then
  ARGS+=(--num-shards "$NUM_SHARDS" --shard-index "${SLURM_ARRAY_TASK_ID:-0}")
fi
if [[ -n "$EXTRA_ARGS" ]]; then
  read -r -a EXTRA_ARRAY <<< "$EXTRA_ARGS"
  ARGS+=("${EXTRA_ARRAY[@]}")
fi
python -m src.run_strategy_eval "${ARGS[@]}"
