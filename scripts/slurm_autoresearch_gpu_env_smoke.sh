#!/usr/bin/env bash
#SBATCH --job-name=ar-gpu-smoke
#SBATCH --partition=mit_normal_gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --output=artifacts/autoresearch_cifar10/slurm/ar-gpu-smoke-%j.out
#SBATCH --error=artifacts/autoresearch_cifar10/slurm/ar-gpu-smoke-%j.err

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
cd "${REPO_ROOT}"
mkdir -p artifacts/autoresearch_cifar10/slurm

echo "started_at=$(date -Is)"
echo "host=$(hostname)"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
command -v nvidia-smi && nvidia-smi || true

export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}"
"${REPO_ROOT}/.venv/bin/python" - <<'PY'
import torch

print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("cuda_device_count", torch.cuda.device_count())
for index in range(torch.cuda.device_count()):
    print("cuda_device", index, torch.cuda.get_device_name(index))
PY

PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}" "${REPO_ROOT}/.venv/bin/python" -m vao.analysis.autoresearch_cifar10_single_trajectory_campaign \
  --config configs/autoresearch_cifar10_model_routing_smoke.yaml \
  --models gpt_5_3_codex_spark \
  --workloads resnet_micro \
  --seeds 9200 \
  --split pilot \
  --steps 1 \
  --max-train-steps 2 \
  --output-root runs/autoresearch_cifar10/slurm_gpu_env_smoke \
  --run-prefix slurm_gpu_env_smoke

echo "finished_at=$(date -Is)"
