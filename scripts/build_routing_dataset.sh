#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src:. python -m vao.training.build_routing_dataset --runs runs/phase4_teacher_opus --out artifacts/phase4_teacher_routing_dataset.jsonl "$@"
