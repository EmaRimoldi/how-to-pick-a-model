#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-src:.}"

LOCAL_RUN_ID="${LOCAL_RUN_ID:-hard_local_smoke}"
HAIKU_RUN_ID="${HAIKU_RUN_ID:-hard_haiku_single_prompt_smoke}"

python -m vao.orchestrator \
  --config configs/hard_local_smoke.yaml \
  --models local_stub \
  --profiles hard_optimization \
  --steps 1 \
  --run-id "$LOCAL_RUN_ID"

python -m vao.validate_run --run_dir "runs/hard_profile/local_smoke/$LOCAL_RUN_ID"
python -m vao.analysis.compute_estimators \
  --runs "runs/hard_profile/local_smoke/$LOCAL_RUN_ID" \
  --out artifacts/hard_local_smoke_estimators.csv
python -m vao.training.build_routing_dataset \
  --runs "runs/hard_profile/local_smoke/$LOCAL_RUN_ID" \
  --out artifacts/hard_local_smoke_routing_dataset.jsonl
python -m vao.analysis.phase3_summary \
  --runs "runs/hard_profile/local_smoke/$LOCAL_RUN_ID" \
  --summary_out artifacts/hard_local_smoke_summary.json \
  --failure_modes_out artifacts/hard_local_smoke_failure_modes.json

if [[ "${RUN_HAIKU:-0}" == "1" ]]; then
  python -m vao.orchestrator \
    --config configs/hard_single_prompt_model_matrix.yaml \
    --models claude_haiku_batch_strict \
    --profiles hard_optimization \
    --steps 1 \
    --run-id "$HAIKU_RUN_ID"

  python -m vao.validate_run --run_dir "runs/hard_profile/single_prompt/model_matrix/$HAIKU_RUN_ID"
  python -m vao.analysis.compute_estimators \
    --runs "runs/hard_profile/single_prompt/model_matrix/$HAIKU_RUN_ID" \
    --out artifacts/hard_haiku_single_prompt_smoke_estimators.csv
  python -m vao.training.build_routing_dataset \
    --runs "runs/hard_profile/single_prompt/model_matrix/$HAIKU_RUN_ID" \
    --out artifacts/hard_haiku_single_prompt_smoke_routing_dataset.jsonl
  python -m vao.analysis.phase3_summary \
    --runs "runs/hard_profile/single_prompt/model_matrix/$HAIKU_RUN_ID" \
    --summary_out artifacts/hard_haiku_single_prompt_smoke_summary.json \
    --failure_modes_out artifacts/hard_haiku_single_prompt_smoke_failure_modes.json
fi
