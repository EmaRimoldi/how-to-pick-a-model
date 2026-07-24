#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:?Set RUN_ID}"
CLUSTER_ROOT="${CLUSTER_ROOT:-/orcd/data/tpoggio/001/erimoldi/theory-of-agents-strategy}"
REMOTE_RUN="$CLUSTER_ROOT/runs/$RUN_ID"
LOCAL_RUN="${LOCAL_RUN:-$PWD/experiment_runs/$RUN_ID}"
POLL_SECONDS="${POLL_SECONDS:-300}"

while ! ssh engaging "test -f '$REMOTE_RUN/COMPLETE'"; do
  if ssh engaging "test -f '$REMOTE_RUN/SUPERVISOR_FAILED'"; then
    echo "Supervisor exhausted retries for $RUN_ID" >&2
    exit 1
  fi
  ssh engaging "printf '%s cells=' \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"; \
    find '$REMOTE_RUN/raw' -name 'strategy_*.jsonl' -print0 | xargs -0 -r cat | wc -l; \
    squeue -j 17715233,17715234,17715235,17717336 -r -h -o '%i %t %M %R' | \
      awk '\$2 == \"R\" {print \"  running \" \$0}'"
  sleep "$POLL_SECONDS"
done

mkdir -p "$LOCAL_RUN"
rsync -az "engaging:$REMOTE_RUN/" "$LOCAL_RUN/"
python - "$LOCAL_RUN/config/strategy_experiment.yaml" "$LOCAL_RUN/config/strategy_experiment.local.yaml" "$LOCAL_RUN" <<'PY'
from pathlib import Path
import sys
import yaml

source, target, root = map(Path, sys.argv[1:])
config = yaml.safe_load(source.read_text(encoding="utf-8"))
config["paths"].update(
    raw=str(root / "raw"),
    derived=str(root / "derived"),
    figures=str(root / "figures"),
)
target.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
PY
python -m src.plot_strategy_results \
  --config "$LOCAL_RUN/config/strategy_experiment.local.yaml" \
  --run-id "$RUN_ID"
echo "Local finalization complete: $LOCAL_RUN"
