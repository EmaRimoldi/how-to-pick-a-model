#!/bin/bash
#SBATCH --job-name=sai3-schedule
#SBATCH --partition=mit_preemptable
#SBATCH --gpus=l40s:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=runs/slurm-%x-%j.out

set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "usage: sbatch $0 MODEL TASKS_JSONL DESIGN_JSONL OUTPUT_DIR" >&2
  exit 2
fi

MODEL="$1"
TASKS="$2"
DESIGN="$3"
OUTPUT_DIR="$4"
BUNDLE="${SAI3_BUNDLE:-${SLURM_SUBMIT_DIR:-$PWD}/experiments/four-term-packed-validation}"
ENV_DIR="${SAI3_ENV_DIR:-$HOME/orcd/scratch/sai3-runtime/.venv}"

if [[ ! -f "$BUNDLE/scripts/run_sai3_schedule.py" ]]; then
  echo "SAI-3 bundle not found at $BUNDLE" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR" "$HOME/orcd/scratch/huggingface" "$HOME/orcd/scratch/uv-cache"
export HF_HOME="$HOME/orcd/scratch/huggingface"
export UV_CACHE_DIR="$HOME/orcd/scratch/uv-cache"
export TOKENIZERS_PARALLELISM=false

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  mkdir -p "$(dirname "$ENV_DIR")"
  uv venv --python 3.11 "$ENV_DIR"
fi

if ! "$ENV_DIR/bin/python" -c "import vllm, transformers" >/dev/null 2>&1; then
  uv pip install --python "$ENV_DIR/bin/python" "vllm>=0.8,<0.12" "transformers>=4.51" numpy
fi

"$ENV_DIR/bin/python" "$BUNDLE/scripts/run_sai3_schedule.py" \
  --tasks "$TASKS" \
  --design "$DESIGN" \
  --model "$MODEL" \
  --trajectories-output "$OUTPUT_DIR/trajectories.jsonl" \
  --slots-output "$OUTPUT_DIR/slots.jsonl" \
  --metadata-output "$OUTPUT_DIR/run_metadata.json" \
  --max-slots "${SAI3_MAX_SLOTS:-128}" \
  --max-tokens "${SAI3_MAX_TOKENS:-256}"
