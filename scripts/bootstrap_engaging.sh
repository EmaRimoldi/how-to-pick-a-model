#!/usr/bin/env bash
# Bootstrap the cluster Python environment for HumanEval+/MBPP+/BBH routing runs.
set -euo pipefail

ROOT="${1:-/orcd/data/tpoggio/001/erimoldi/theory-of-agents-strategy}"
cd "$ROOT"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/orcd/data/tpoggio/001/erimoldi/uv-cache}"
export HF_HOME="${HF_HOME:-/orcd/data/tpoggio/001/erimoldi/huggingface}"
mkdir -p "$UV_CACHE_DIR" "$HF_HOME"

if [[ ! -x .venv/bin/python ]]; then
  "$HOME/.local/bin/uv" python install 3.11
  "$HOME/.local/bin/uv" venv --python 3.11 .venv
fi

"$HOME/.local/bin/uv" pip install --python .venv/bin/python -r requirements-cluster.txt
.venv/bin/python - <<'PY'
import evalplus
import numpy
import scipy
import torch
import transformers
print("torch", torch.__version__, "cuda", torch.version.cuda)
print("transformers", transformers.__version__)
print("evalplus", getattr(evalplus, "__version__", "unknown"))
PY
