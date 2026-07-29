#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_FULL_RUN:-}" != "YES" ]]; then
  echo "Set CONFIRM_FULL_RUN=YES after authorizing the GPU-hour budget." >&2
  exit 2
fi

ROOT="${ROOT:-/home/erimoldi/openclaw_remote/projects/NeurIPS_2026}"
RUN_ID="${RUN_ID:-full-$(date -u +%Y%m%dT%H%M%SZ)}"
NUM_SHARDS="${NUM_SHARDS:-8}"
ARRAY_LIMIT="${ARRAY_LIMIT:-1}"
PARTITION="${PARTITION:-ou_bcs_low}"
EXPERIMENT_ROOT="$ROOT/experiments/humaneval-plus/strategy-by-difficulty-grid"
RUN_ROOT="$EXPERIMENT_ROOT/runs/$RUN_ID"
CONFIG_PATH="$RUN_ROOT/config/strategy_experiment.yaml"

cd "$ROOT"
mkdir -p "$RUN_ROOT"/{config,raw,derived,figures,logs,manuscript}
source .venv/bin/activate
python - "$EXPERIMENT_ROOT/configs/strategy_experiment.yaml" "$CONFIG_PATH" "$RUN_ROOT" <<'PY'
from pathlib import Path
import sys
import yaml

source, target, run_root = map(Path, sys.argv[1:])
config = yaml.safe_load(source.read_text(encoding="utf-8"))
config["paths"].update({
    "raw": str(run_root / "raw"),
    "derived": str(run_root / "derived"),
    "figures": str(run_root / "figures"),
})
target.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
PY
cp requirements-cluster.txt "$RUN_ROOT/config/requirements-cluster.txt"
tar -czf "$RUN_ROOT/config/source_snapshot.tar.gz" \
  src \
  experiments/humaneval-plus/strategy-by-difficulty-grid/scripts \
  experiments/humaneval-plus/strategy-by-difficulty-grid/configs \
  requirements-cluster.txt
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git rev-parse HEAD > "$RUN_ROOT/config/git_commit.txt"
  git diff > "$RUN_ROOT/config/uncommitted.patch"
else
  printf '%s\n' 'cluster snapshot is not a Git worktree; see source_snapshot.tar.gz' \
    > "$RUN_ROOT/config/git_commit.txt"
  : > "$RUN_ROOT/config/uncommitted.patch"
fi
printf '%s\n' "$RUN_ID" > "$RUN_ROOT/RUN_ID"

job_ids=()
for model in 1.5b 7b 32b; do
  output="$({
    MODEL_KEY="$model" RUN_ID="$RUN_ID" NUM_SHARDS="$NUM_SHARDS" CONFIG_PATH="$CONFIG_PATH" \
      sbatch \
        --partition="$PARTITION" \
        --array="0-$((NUM_SHARDS - 1))%${ARRAY_LIMIT}" \
        --output="$RUN_ROOT/logs/%x-%A_%a.out" \
        --error="$RUN_ROOT/logs/%x-%A_%a.err" \
        --export=ALL \
        experiments/humaneval-plus/strategy-by-difficulty-grid/scripts/slurm_strategy_worker.sbatch
  })"
  job_id="${output##* }"
  job_ids+=("$job_id")
  echo "$model workers: $job_id"
done

dependency=$(IFS=:; echo "${job_ids[*]}")
analysis_output=$(RUN_ID="$RUN_ID" CONFIG_PATH="$CONFIG_PATH" sbatch \
  --dependency="afterok:$dependency" \
  --output="$RUN_ROOT/logs/%x-%j.out" \
  --error="$RUN_ROOT/logs/%x-%j.err" \
  --export=ALL \
  experiments/humaneval-plus/strategy-by-difficulty-grid/scripts/slurm_strategy_analyze.sbatch)
analysis_job="${analysis_output##* }"
echo "analysis: $analysis_job"
echo "run_id: $RUN_ID"
echo "run_root: $RUN_ROOT"
python - "$RUN_ROOT/config/jobs.json" "$RUN_ID" "$PARTITION" "$NUM_SHARDS" "$ARRAY_LIMIT" "$analysis_job" "${job_ids[@]}" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

path, run_id, partition, shards, array_limit, analysis, *workers = sys.argv[1:]
payload = {
    "run_id": run_id,
    "submitted_utc": datetime.now(timezone.utc).isoformat(),
    "partition": partition,
    "num_shards": int(shards),
    "array_limit_per_model": int(array_limit),
    "worker_jobs": dict(zip(("1.5b", "7b", "32b"), workers, strict=True)),
    "analysis_job": analysis,
}
Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
