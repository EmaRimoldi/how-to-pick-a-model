#!/usr/bin/env bash
#SBATCH --job-name=toa-router
#SBATCH --partition=ou_bcs_low
#SBATCH --gres=gpu:h100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=96G
#SBATCH --time=6:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

ROOT="${ROOT:-/orcd/data/tpoggio/001/erimoldi/theory-of-agents-strategy}"
RUN_ID="${RUN_ID:?Set RUN_ID}"
CONFIG_PATH="${CONFIG_PATH:-config/strategy_experiment.yaml}"
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

source .venv/bin/activate
python -m src.run_strategy_router \
  --config "$CONFIG_PATH" \
  --run-id "$RUN_ID" \
  $EXTRA_ARGS
