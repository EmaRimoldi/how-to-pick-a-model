#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-src:.}"

RUN_ID_PREFIX="${RUN_ID_PREFIX:-paper_profile_local_validation_r0}"
RUN_ROOT="runs/paper_profile_validation/local"

python -m vao.analysis.profile_split_audit \
  --out artifacts/profile_split_audit.json \
  --md_out artifacts/profile_split_audit.md

python -m vao.orchestrator \
  --config configs/paper_profile_local_validation.yaml \
  --models local_stub \
  --run-id "$RUN_ID_PREFIX"

while IFS= read -r run_dir; do
  python -m vao.validate_run --run_dir "$run_dir"
done < <(find "$RUN_ROOT" -maxdepth 1 -type d -name "${RUN_ID_PREFIX}_*" | sort)

python -m vao.analysis.compute_estimators \
  --runs "$RUN_ROOT" \
  --out artifacts/paper_profile_validation_estimators.csv

python -m vao.training.build_routing_dataset \
  --runs "$RUN_ROOT" \
  --out artifacts/paper_profile_validation_routing_all.jsonl

python -m vao.training.build_routing_dataset \
  --runs "$RUN_ROOT" \
  --exclude_holdout \
  --out artifacts/paper_profile_validation_routing_dev_only.jsonl

python -m vao.analysis.phase3_summary \
  --runs "$RUN_ROOT" \
  --summary_out artifacts/paper_profile_validation_summary.json \
  --failure_modes_out artifacts/paper_profile_validation_failure_modes.json
