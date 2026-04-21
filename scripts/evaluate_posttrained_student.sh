#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src:. python -m vao.training.evaluate_student \
  --model_path training/phase5_routing_student/model.pkl \
  --records artifacts/phase4_teacher_routing_dataset.jsonl \
  --out artifacts/phase5_routing_eval_summary.json \
  --predictions_out training/phase5_routing_student/eval_predictions_full.json "$@"
