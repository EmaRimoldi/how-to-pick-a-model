#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-src:.}"

BASE_URL="${OPENAI_COMPATIBLE_BASE_URL:-http://localhost:8000/v1}"
RUN_ID="${RUN_ID:-hard_qwen_direct_smoke_1step}"

python - <<'PY'
import json
import os
import urllib.request

base_url = os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000/v1").rstrip("/")
with urllib.request.urlopen(f"{base_url}/models", timeout=30) as response:
    payload = json.loads(response.read().decode("utf-8"))
print(json.dumps({"endpoint": base_url, "models": payload.get("data", [])[:3]}, indent=2))
PY

python -m vao.orchestrator \
  --config configs/hard_qwen_direct_10step.yaml \
  --models weak_qwen_direct \
  --profiles hard_optimization \
  --steps 1 \
  --run-id "${RUN_ID}"

python -m vao.validate_run --run_dir "runs/hard_profile/haiku_vs_qwen/qwen_direct/${RUN_ID}"
