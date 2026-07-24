# Experiment Reproducibility Matrix

This page is the canonical map from experiment evidence to the commands and
environment needed to reproduce it.

## Global Setup

Base package, tests, CLI, reports, and figure scripts:

```bash
uv sync --dev --frozen
uv run pytest tests -q
uv run agent-workflow demo --output-dir /tmp/agent-workflow-demo --experiment-id repro_demo --force
```

Optional experiment dependency profiles:

```bash
# CIFAR-10 AutoResearch evaluator: torch, torchvision
uv sync --dev --extra autoresearch --frozen

# SWE-bench scaffold tooling: datasets, docker, swebench, tqdm
uv sync --dev --extra swebench --frozen

# Embedding and weight-space diversity metrics
uv sync --dev --extra analysis-ml --frozen

# Everything above
uv sync --dev --extra all-experiments --frozen
```

The repository intentionally does not commit `.venv/`, `.pytest_cache/`,
`__pycache__/`, local datasets, raw `runs/`, or Slurm logs. `uv.lock` is the
locked Python dependency source. `.env` is local-only; use `.env.example` as the
template.

External tools for live reruns:

- `claude` CLI from Claude Code, authenticated and on `PATH`.
- Git.
- Network access for first-time dataset downloads.
- Optional Slurm/GPU access for long live-agent runs.
- Docker or Modal for official SWE-bench evaluation.

## Experiment Status

| Experiment | Evidence in repo | Reproducible from this repo | Command |
| --- | --- | --- | --- |
| `01_baseline` | Tables, JSON summary, figures, figure script, current `autoresearch/` task | Figures are reproducible. Full calibration rerun is possible with the AutoResearch extra and CIFAR-10 download. | `uv run python scripts/plot_baseline.py` |
| `02_evaluation_protocol_calibration` | Fixed-time/fixed-step summary CSV/JSON, archived pilot JSON, figures, figure script | Figures are reproducible. The original CPU benchmark runners are not tracked as standalone launch scripts; rerun methodology is documented by the tables. | `uv run python scripts/plot_evaluation_protocol_calibration.py` |
| `03_agent_memory_ablation` | Canonical trial JSON, statistical summary, figures, figure script | Figures are reproducible. Historical live Claude runs are not bit-for-bit reproducible and raw live directories are not included. | `uv run python scripts/plot_agent_memory_ablation.py` |
| `04_swarm_baselines` | Historical summaries, analysis scripts, CSV/JSON, figures, figure script | Public figures are reproducible. Some archived deep-dive scripts require raw run trees that were not present when curated. New swarm runs can be launched with the current CLI. | `uv run python scripts/plot_swarm_baselines.py` |
| `05_autoresearch_model_routing` | Processed accounting, 250 minimal raw traces, config snapshot, figure scripts, figures | Processed figure regeneration and raw-trace inspection are reproducible. The 270-record table is complete; raw JSONL coverage is 180 balanced records. | see commands below |
| `06_swebench_experimental_scaffold` | Neutral SWE-bench 100-instance scaffold, configs, prompts, orchestration implementation | This is a scaffold, not a completed result bundle. The implementation lives under `vao_swebench_orchestration` and needs namespace cleanup before direct execution. | see commands below |

## Experiment Commands

### 01 Baseline

Regenerate public figures from checked-in CSV/JSON tables:

```bash
uv run python scripts/plot_baseline.py
```

Rerun a fresh baseline calibration. This downloads CIFAR-10 on first use and
requires the AutoResearch extra:

```bash
uv sync --dev --extra autoresearch --frozen
uv run agent-workflow baseline-calibration \
  --autoresearch-dir autoresearch \
  --out-dir runs/reproduce_baseline_1170 \
  --train-max-steps 1170 \
  --train-time-budget 300 \
  --timeout 900
```

### 02 Evaluation Protocol Calibration

Regenerate public figures from checked-in fixed-time and fixed-step summaries:

```bash
uv run python scripts/plot_evaluation_protocol_calibration.py
```

The current repository tracks the benchmark result tables, not the original
standalone CPU benchmark launch scripts that created every raw measurement.

### 03 Agent Memory Ablation

Regenerate public figures from the canonical trial JSON:

```bash
uv run python scripts/plot_agent_memory_ablation.py
```

New live comparisons should use fixed-step evaluation:

```bash
uv sync --dev --extra autoresearch --frozen
uv run agent-workflow parallel-shared \
  --config configs/experiment.yaml \
  --time-budget 30 \
  --train-budget 300 \
  --n-agents 2 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id memory_ablation_rerun
```

### 04 Swarm Baselines

Regenerate public figures:

```bash
uv run python scripts/plot_swarm_baselines.py
```

Run a new integrated swarm smoke:

```bash
uv sync --dev --extra autoresearch --frozen
uv run agent-workflow swarm \
  --run \
  --config configs/experiment.yaml \
  --time-budget 10 \
  --train-budget 120 \
  --n-agents 2 \
  --experiment-id swarm_smoke
```

### 05 AutoResearch Model Routing

Regenerate processed figures from the analysis JSON:

```bash
(
  cd experiments/autoresearch/05_autoresearch_model_routing
  uv run python source/scripts/reproduce_main_figures_from_processed.py \
    --input results/accounting/threeworker_final_analysis.json \
    --out-dir results/figures/reproduced
)
```

Inspect raw-trace coverage:

```bash
uv run python - <<'PY'
import csv
from collections import Counter
path = "experiments/autoresearch/05_autoresearch_model_routing/raw/manifests/balanced_n30_raw_coverage.csv"
with open(path, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
print(Counter(row["raw_status"] for row in rows))
print(Counter((row["condition"], row["backbone"], row["raw_status"]) for row in rows))
PY
```

Validate that JSON/JSONL raw traces parse:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
root = Path("experiments/autoresearch/05_autoresearch_model_routing/raw")
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

### 06 SWE-bench Experimental Scaffold

Install the SWE-bench support dependencies:

```bash
uv sync --dev --extra swebench --frozen
```

Inspect the prompt-safe public slice and configs:

```bash
head -2 experiments/other/swebench-experimental-scaffold/source/study/data/verified_100/instances_public.jsonl
uv run python -m json.tool \
  experiments/other/swebench-experimental-scaffold/source/study/data/verified_100/download_manifest.json
```

The scaffold implementation currently expects the `vao.swebench_orchestration.*`
namespace. Before direct execution, either restore that namespace package or
adapt imports to the current runtime package. No completed SWE-bench result
bundle is tracked yet.

## Audit Notes

- Tracked raw AutoResearch files are covered by
  `05_autoresearch_model_routing/raw/manifests/raw_file_manifest_sha256.csv`.
- Local `.venv/` exists on this machine but is ignored. Recreate it with `uv`.
- Local `.pytest_cache/`, `.DS_Store`, and `__pycache__/` are ignored and are not
  reproducibility artifacts.
- Any future experiment should include: exact command, config file, input data
  path, output directory, dependency extra, expected artifact list, and whether
  live model calls are required.
