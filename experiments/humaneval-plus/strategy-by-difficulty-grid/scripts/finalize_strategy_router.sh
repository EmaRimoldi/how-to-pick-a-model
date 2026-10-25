#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:?Set RUN_ID}"
ROUTER_PID="${ROUTER_PID:?Set ROUTER_PID}"
LOCAL_ROOT="${LOCAL_ROOT:-$PWD/experiments/humaneval-plus/strategy-by-difficulty-grid/runs/$RUN_ID}"
CLUSTER_ROOT="${CLUSTER_ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
CLUSTER_RUN="$CLUSTER_ROOT/experiments/humaneval-plus/strategy-by-difficulty-grid/runs/$RUN_ID"
ROUTER_FILE="$LOCAL_ROOT/raw/router_$RUN_ID.jsonl"

while kill -0 "$ROUTER_PID" 2>/dev/null; do
  sleep 30
done

python - "$ROUTER_FILE" "$RUN_ID" <<'PY'
import json
import sys

path, run_id = sys.argv[1:]
rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
keys = {
    (row["fold"], row["context_examples"], row["task_id"], row["model_key"])
    for row in rows
    if row.get("run_id") == run_id
}
expected = 164 * 3 * 3
if len(rows) != expected or len(keys) != expected:
    raise SystemExit(f"incomplete router: rows={len(rows)}, unique={len(keys)}, expected={expected}")
print(f"validated {expected} router decisions")
PY

rsync -az "$ROUTER_FILE" "engaging:$CLUSTER_RUN/raw/"
rsync -az "$LOCAL_ROOT/raw/router_output_schema.json" "$LOCAL_ROOT/raw/strategy_folds.json" \
  "engaging:$CLUSTER_RUN/config/"
ssh engaging "cd '$CLUSTER_ROOT' && source .venv/bin/activate && \
  python -m src.analyze_strategy_router \
    --config '$CLUSTER_RUN/config/strategy_experiment.yaml' --run-id '$RUN_ID'"
echo "router finalized for $RUN_ID"
