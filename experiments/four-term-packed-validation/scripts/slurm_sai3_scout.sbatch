#!/bin/bash
#SBATCH --job-name=sai3-scout
#SBATCH --partition=mit_preemptable
#SBATCH --gpus=l40s:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=runs/slurm-%x-%j.out

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: sbatch $0 MODEL TASKS_JSONL OUTPUT_DIR" >&2
  exit 2
fi

MODEL="$1"
TASKS="$2"
OUTPUT_DIR="$3"
BUNDLE="$(cd "$(dirname "$0")/.." && pwd)"
ENV_DIR="${SAI3_ENV_DIR:-$HOME/orcd/scratch/sai3-runtime/.venv}"

mkdir -p "$OUTPUT_DIR" "$HOME/orcd/scratch/huggingface" "$HOME/orcd/scratch/uv-cache"
export HF_HOME="$HOME/orcd/scratch/huggingface"
export UV_CACHE_DIR="$HOME/orcd/scratch/uv-cache"
export TOKENIZERS_PARALLELISM=false

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  mkdir -p "$(dirname "$ENV_DIR")"
  uv venv --python 3.11 "$ENV_DIR"
  uv pip install --python "$ENV_DIR/bin/python" "vllm>=0.8,<0.12" "transformers>=4.51" numpy
fi

"$ENV_DIR/bin/python" "$BUNDLE/scripts/run_sai3_scout.py" \
  --tasks "$TASKS" \
  --model "$MODEL" \
  --output "$OUTPUT_DIR/completions.jsonl" \
  --metadata-output "$OUTPUT_DIR/run_metadata.json" \
  --tasks-per-mode "${SAI3_TASKS_PER_MODE:-6}" \
  --matched-attempts "${SAI3_MATCHED_ATTEMPTS:-4}" \
  --wrong-attempts "${SAI3_WRONG_ATTEMPTS:-1}"
