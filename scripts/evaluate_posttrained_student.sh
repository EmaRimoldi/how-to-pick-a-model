#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src:. python -m vao.training.evaluate_student --adapter artifacts/qwen_routing_lora --config configs/phase1_holdout.yaml --out runs/qwen_routing_lora_holdout "$@"
