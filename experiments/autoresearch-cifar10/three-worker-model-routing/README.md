# AutoResearch Model Routing

This experiment studies AutoResearch workload routing across three CIFAR-10
workload families and three worker aliases. It contains processed accounting
tables, public figures, config snapshots, and a minimal raw trace bundle.

## Scope

The processed routing table records:

- Workloads: `mlp_flat`, `cnn_compact`, `resnet_micro`.
- Workers: `gpt_5_3_codex`, `gpt_5_4`, `gpt_5_4_mini`.
- Trials: 30 per workload/worker cell.
- Run horizon: 20 proposal/evaluation steps per run.
- Total processed records: `3 x 3 x 30 = 270`.

The checked-in raw trace bundle covers 180 of the 270 balanced records: trials
`011`-`030` for every workload/worker cell. Trials `001`-`010` are represented
in processed accounting tables but do not have raw JSONL traces in this tree.

## Task

Each AutoResearch run starts from a small CIFAR-10 training program. The worker
proposes structured edits to the candidate solution, the harness applies the
edit, runs a verifier, and records validation loss. Lower validation loss is
better.

## Success Threshold

The main threshold is `0.05`, meaning at least 5% relative validation-loss
improvement versus the starting candidate:

```text
relative_improvement = (baseline_loss - best_loss) / baseline_loss
success = relative_improvement >= 0.05
```

`tau_step` is the first proposal step at which a run reaches that threshold. A
lower `tau_step` means the worker found a useful edit earlier.

## Reader-Facing Metrics

Use these metrics when presenting this experiment:

- `success_count` / `success_rate`: how often a worker reaches the 5%
  validation-loss improvement threshold within 20 steps.
- `mean_tau`: average first successful step among successful runs.
- `mean_final_relative_improvement`: average best validation-loss improvement
  by the end of the 20-step run.
- `mean_elapsed_wall_minutes`: observed wall-clock runtime.
- `mean_total_tokens_millions`: token usage reported by the run accounting.

The README and current public figures use direct success, time, token, and
improvement metrics.

## Main Observed Results

- The balanced processed table contains 270 records.
- At threshold `0.05`, 263 of 270 processed records crossed the success
  threshold within 20 steps.
- Raw trace coverage is 180/270 balanced records.
- Raw traces are complete for the 180 covered records: each contains
  `evaluations.jsonl`, `run_summary.json`, config snapshots, and prompt/session
  metadata.

## Reproduction Code

Safe verification commands:

```bash
uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/agent_workflow_autoresearch_reproduced
uv run python scripts/plot_autoresearch_readme_figures.py
uv run python scripts/plot_product_evidence_assets.py
```

Inspect raw-trace coverage:

```bash
uv run python - <<'PY'
import csv
from collections import Counter
path = "experiments/autoresearch-cifar10/three-worker-model-routing/raw/manifests/balanced_n30_raw_coverage.csv"
with open(path, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
print(Counter(row["raw_status"] for row in rows))
print(Counter((row["condition"], row["backbone"], row["raw_status"]) for row in rows))
PY
```

Validate JSON and JSONL traces:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
root = Path("experiments/autoresearch-cifar10/three-worker-model-routing/raw")
count = 0
for path in root.rglob("*"):
    if path.suffix == ".json":
        json.loads(path.read_text(encoding="utf-8"))
        count += 1
    elif path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    json.loads(line)
                    count += 1
print(f"parsed records/files: {count}")
PY
```

## What Is Not Included

- Full transient worker directories.
- Broken or environment-specific symlink trees.
- Cluster scheduler logs.
- Provider-side transcripts not already captured in the raw trace bundle.

This means the processed 270-record result table is available, but only the 180
covered records can be audited step-by-step from raw JSONL traces.

## Read First

- `results/accounting/threeworker_balanced_n30_frontier_summary.csv`
- `results/accounting/threeworker_threshold_summary.csv`
- `results/accounting/threeworker_router_gain_summary.csv`
- `raw/manifests/raw_run_inventory.csv`
- `source/exploratory-bottleneck-pilot.md`: historical six-mode, four-worker
  pilot decisions that preceded the promoted panel.
- `raw/README.md`
- `results/figures/README.md`
