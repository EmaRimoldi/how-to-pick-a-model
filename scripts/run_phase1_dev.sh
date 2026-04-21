#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src:. python -m vao.orchestrator --config configs/phase1_dev.yaml "$@"
