#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PYTHONPATH_VALUE="src:."
PYTHON_BIN="./.venv/bin/python"
SOLVER_ROOT="autoresearch/runs/router_cnn4096_solver"
PROBE_ROOT="autoresearch/runs/router_cnn4096_probe"
ARTIFACT_ROOT="autoresearch/artifacts"

# name split seed train_subset label_noise imbalance_ratio
CONDITIONS=(
  "base_pilot pilot 9801 50000 0.0 1"
  "lowdata_pilot pilot 9802 5000 0.0 1"
  "noisy_pilot pilot 9803 50000 0.1 1"
  "imbalanced_pilot pilot 9804 50000 0.0 5"
  "base_holdout holdout 9901 50000 0.0 1"
  "lowdata_holdout holdout 9902 5000 0.0 1"
  "noisy_holdout holdout 9903 50000 0.1 1"
  "imbalanced_holdout holdout 9904 50000 0.0 5"
)

for row in "${CONDITIONS[@]}"; do
  read -r NAME SPLIT SEED TRAIN_SUBSET LABEL_NOISE IMBALANCE <<<"$row"

  PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_pilot \
    --config autoresearch/configs/autoresearch_cifar10_cnn4096_router_solver.yaml \
    --models claude_haiku,claude_sonnet,claude_opus_4_6 \
    --workloads cnn_compact \
    --seeds "$SEED" \
    --split "$SPLIT" \
    --output-root "$SOLVER_ROOT" \
    --run-prefix "routersolve_${NAME}" \
    --max-train-steps 4096 \
    --train-subset-size "$TRAIN_SUBSET" \
    --label-noise-rate "$LABEL_NOISE" \
    --imbalance-ratio "$IMBALANCE"

  PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_pilot \
    --config autoresearch/configs/autoresearch_cifar10_cnn4096_router_probe.yaml \
    --models claude_haiku \
    --workloads cnn_compact \
    --seeds "$SEED" \
    --split "$SPLIT" \
    --steps 1 \
    --output-root "$PROBE_ROOT" \
    --run-prefix "routerprobe1_${NAME}" \
    --max-train-steps 4096 \
    --train-subset-size "$TRAIN_SUBSET" \
    --label-noise-rate "$LABEL_NOISE" \
    --imbalance-ratio "$IMBALANCE"

  PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_pilot \
    --config autoresearch/configs/autoresearch_cifar10_cnn4096_router_probe.yaml \
    --models claude_haiku \
    --workloads cnn_compact \
    --seeds "$SEED" \
    --split "$SPLIT" \
    --steps 2 \
    --output-root "$PROBE_ROOT" \
    --run-prefix "routerprobe2_${NAME}" \
    --max-train-steps 4096 \
    --train-subset-size "$TRAIN_SUBSET" \
    --label-noise-rate "$LABEL_NOISE" \
    --imbalance-ratio "$IMBALANCE"
done

PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_workload_accounting \
  "$SOLVER_ROOT" \
  --router-feature-set workload_only \
  --cost-metric wall_seconds \
  --pilot-split pilot \
  --holdout-split holdout \
  --output "$ARTIFACT_ROOT/router_cnn4096_workload_only.json"

PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_workload_accounting \
  "$SOLVER_ROOT" \
  --router-feature-set workload_plus_probe \
  --cost-metric wall_seconds \
  --pilot-split pilot \
  --holdout-split holdout \
  --output "$ARTIFACT_ROOT/router_cnn4096_workload_plus_probe.json"

PYTHONPATH="$PYTHONPATH_VALUE" "$PYTHON_BIN" -m autoresearch.analysis.autoresearch_cifar10_workload_accounting \
  "$SOLVER_ROOT" \
  --probe-roots "$PROBE_ROOT" \
  --router-feature-set workload_plus_interactions \
  --cost-metric wall_seconds \
  --pilot-split pilot \
  --holdout-split holdout \
  --output "$ARTIFACT_ROOT/router_cnn4096_workload_plus_interactions.json"
