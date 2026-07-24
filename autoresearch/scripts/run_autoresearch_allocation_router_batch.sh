#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CAMPAIGN_ROOT="${CAMPAIGN_ROOT:-$PROJECT_ROOT/autoresearch/campaigns/h20_delta005_20260505}"
EXP_DIR="${EXP_DIR:-$CAMPAIGN_ROOT/router_allocation/allocation_3routers_xhigh_z012_20260529}"
RUN_ROOT="${RUN_ROOT:-$CAMPAIGN_ROOT/runs/worker_pilot}"

ROUTER_KEYS=("$@")
if [[ "${#ROUTER_KEYS[@]}" -eq 0 ]]; then
  ROUTER_KEYS=(gpt_5_5_router_xhigh gpt_5_4_router_xhigh gpt_5_4_mini_router_xhigh)
fi

SEED_CHUNKS=(
  "9300,9301"
  "9302,9303"
  "9304,9305"
  "9306,9307"
  "9308,9309"
)

cd "$PROJECT_ROOT"
mkdir -p "$EXP_DIR/chunks" "$EXP_DIR/merged" "$EXP_DIR/logs"

for ROUTER_KEY in "${ROUTER_KEYS[@]}"; do
  CHUNK_DIR="$EXP_DIR/chunks/$ROUTER_KEY"
  mkdir -p "$CHUNK_DIR"
  for SEEDS in "${SEED_CHUNKS[@]}"; do
    LABEL="${SEEDS/,/_}"
    OUT="$CHUNK_DIR/router_${ROUTER_KEY}_${LABEL}.jsonl"
    COUNT=0
    if [[ -f "$OUT" ]]; then
      COUNT="$(wc -l < "$OUT" | tr -d ' ')"
    fi
    if [[ "$COUNT" == "18" ]]; then
      echo "[$(date -Is)] skip complete router=$ROUTER_KEY seeds=$SEEDS output=$OUT"
      continue
    fi
    echo "[$(date -Is)] start router=$ROUTER_KEY seeds=$SEEDS output=$OUT"
    PYTHONPATH=src:. "$PROJECT_ROOT/.venv/bin/python" -m autoresearch.analysis.autoresearch_cifar10_router_decisions \
      --output "$OUT" \
      --router-model-key "$ROUTER_KEY" \
      --candidate-agent-models gpt_5_3_codex,gpt_5_4,gpt_5_4_mini \
      --workloads mlp_flat,cnn_compact,resnet_micro \
      --seeds "$SEEDS" \
      --signals Z0,Z1,Z2 \
      --controls none \
      --scout-steps 2 \
      --router-contract allocation \
      --hide-mode-labels \
      --run-roots "$RUN_ROOT"
    echo "[$(date -Is)] done router=$ROUTER_KEY seeds=$SEEDS output=$OUT"
  done

  cat "$CHUNK_DIR"/router_"$ROUTER_KEY"_*.jsonl > "$EXP_DIR/merged/router_decisions_${ROUTER_KEY}.jsonl"
  echo "[$(date -Is)] merged router=$ROUTER_KEY output=$EXP_DIR/merged/router_decisions_${ROUTER_KEY}.jsonl"
done
