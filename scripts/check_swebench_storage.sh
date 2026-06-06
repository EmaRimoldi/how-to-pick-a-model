#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
SWEBENCH_ROOT="${SWEBENCH_ROOT:-${REPO_ROOT}/swebench}"

cd "${REPO_ROOT}"

echo "== quota =="
quota -s 2>/dev/null || quota -v 2>/dev/null || true

echo
echo "== filesystem =="
df -h /home/erimoldi | sed -n '1,5p'

echo
echo "== swebench storage =="
for path in \
  "${REPO_ROOT}/.hf_cache" \
  "${REPO_ROOT}/.venv-vllm" \
  "${SWEBENCH_ROOT}" \
  "${REPO_ROOT}/experiments/swebench_orchestration" \
  "${REPO_ROOT}/src/vao/swebench_orchestration"; do
  if [[ -e "${path}" ]]; then
    du -sh "${path}" 2>/dev/null
  fi
done | sort -h

echo
echo "== top repo dirs =="
du -sh "${REPO_ROOT}"/* 2>/dev/null | sort -h | tail -n 20
