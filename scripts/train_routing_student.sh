#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src:. python -m vao.training.train_routing_lora --config configs/routing_training.yaml "$@"
