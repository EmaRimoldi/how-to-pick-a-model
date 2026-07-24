# Reproducibility Guide

This document is the canonical map from tracked evidence to commands, external
tools, and known gaps.

## Environment

The existing local environment was created with `uv` and uses CPython 3.13.12.
It intentionally does not contain `pip`, so use `uv pip` for installs.

```bash
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements.txt
uv pip check --python .venv/bin/python
.venv/bin/python -m compileall -q src
```

Tracked dependency source:

- `requirements.txt`: pinned Python package set.

Ignored local resources:

- `.venv/`
- `__pycache__/`
- `.DS_Store`
- `.pytest_cache/`
- `figures/`
- `report/`
- LaTeX build outputs such as `main.aux`, `main.log`, and `main.pdf`
- smoke-test raw and derived artifacts matched by `.gitignore`
- `.local_archive/`

External runtime tools:

- `ollama`, with a running local Ollama server for worker runs.
- `codex`, only for router/category experiments using the Codex CLI backend.
- Network access for EvalPlus/Hugging Face dataset downloads.

Model pulls for code tasks:

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:32b
```

Model pulls for BBH reasoning tasks:

```bash
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:7b
ollama pull qwen2.5:32b
```

Router runs using `codex_cli` require:

```bash
export ROUTER_MODEL=<codex-model-id>
```

If `router.backend` is changed to `openai_api`, also set `OPENAI_API_KEY`.

## Safe Audit Commands

These commands inspect tracked logs and source code without making model calls or
overwriting tracked results:

```bash
.venv/bin/python -m compileall -q src
.venv/bin/python -m src.load_traces --config config/router_experiment.yaml
.venv/bin/python -m src.load_traces --config config/router_experiment_mbpp_2models.yaml
.venv/bin/python -m src.load_traces --config config/router_experiment_bbh.yaml
```

Observed local read-only trace counts:

- HumanEval+ router config: 164 tasks, 164 rows for each of 1.5B, 7B, and 32B.
- MBPP+ two-model router config: 378 tasks, 378 rows for each of 1.5B and 7B.
- BBH router config: 1200 tasks, 1200 rows for each of 1.5B and 7B.

The full MBPP category config is not read-only reproducible until
`data/derived/mbpp_modes_category.json` is produced by the category tagger.

## Experiment Matrix

| Track | Evidence currently tracked | Reproducible without live model calls | Live/model requirement | Main commands |
| --- | --- | --- | --- | --- |
| HumanEval+ worker frontier | `data/raw/runs_qwen2.5-coder_*_full_20260616T0640Z.jsonl`, `data/derived/modes.json`, `tau_star.json`, `success_curves.json`, `frontier.json` | Estimation and plotting from tracked worker logs | Full rerun requires Ollama and Qwen2.5-Coder 1.5B/7B/32B | `scripts/smoke_test.sh`, `scripts/full_run.sh` |
| HumanEval+ retry router | `data/derived/folds.json`, `router_results.jsonl`, `router_summary.json` | Aggregation/plots from tracked router results | Full router rerun requires Codex CLI or API model in `ROUTER_MODEL` | `scripts/smoke_router.sh`, `scripts/full_router_run.sh` |
| MBPP+ worker logs | tracked 1.5B, 7B, and 32B worker JSONL logs plus `mbpp_modes.json` | Trace loading and worker-log analysis | Full worker rerun requires Ollama Qwen2.5-Coder models | `scripts/smoke_mbpp_worker.sh`, `scripts/full_run_mbpp_2models.sh`, `scripts/full_run_mbpp_32b.sh` |
| MBPP+ two-model router | `config/router_experiment_mbpp_2models.yaml`, `mbpp_folds_2models.json`; router results are ignored/local by current `.gitignore` | Trace loading only from tracked files | Router rerun requires Codex CLI/API and writes ignored local outputs | `src.run_router_experiment`, `src.estimate_router`, `src.plot_router` with the MBPP two-model config |
| MBPP+ category router | category smoke artifacts exist locally but are ignored; full category labels are not tracked | Not complete from tracked files because `mbpp_modes_category.json` is absent | Run category tagger first, then router/frontier | `scripts/smoke_category.sh`, `scripts/full_category_run.sh` |
| BBH worker logs | tracked 1.5B and 7B BBH logs, `bbh_modes*.json`, `bbh_mode_groups.json` | Trace loading and BBH mode inspection | Full worker script expects 1.5B/7B/32B; tracked router config currently uses 1.5B/7B only | `scripts/smoke_bbh.sh`, `scripts/full_run_bbh.sh` |
| BBH router/frontier | config exists; full router result files are not tracked | Trace loading only from tracked files | Full router rerun requires Codex CLI/API | `scripts/full_router_run_bbh.sh` |

## Regenerating Derived Outputs

HumanEval+ worker estimates and figures from tracked worker logs:

```bash
.venv/bin/python -m src.estimate --config config/experiment.yaml
.venv/bin/python -m src.plot --config config/experiment.yaml
```

HumanEval+ router summary and figures from tracked router results:

```bash
.venv/bin/python -m src.estimate_router --config config/router_experiment.yaml
.venv/bin/python -m src.plot_router --config config/router_experiment.yaml
```

MBPP+ two-model router, if local router results are present or after rerunning
the router:

```bash
.venv/bin/python -m src.run_router_experiment \
  --config config/router_experiment_mbpp_2models.yaml \
  --mock-router \
  --folds 0 \
  --limit-test-problems 5 \
  --overwrite
.venv/bin/python -m src.estimate_router --config config/router_experiment_mbpp_2models.yaml
.venv/bin/python -m src.plot_router --config config/router_experiment_mbpp_2models.yaml
```

BBH router/frontier, after router results have been produced:

```bash
.venv/bin/python -m src.estimate_router --config config/router_experiment_bbh.yaml
.venv/bin/python -m src.plot_router --config config/router_experiment_bbh.yaml
.venv/bin/python -m src.frontier_by_category \
  --config config/router_experiment_bbh.yaml \
  --figure-stem fig_bbh_family_frontier
```

## Smoke Script Warning

Some smoke scripts are intentionally destructive for local smoke outputs:

- `scripts/smoke_test.sh` removes and regenerates `data/raw/*smoke*` and writes
  canonical `data/derived/tau_star.json`, `success_curves.json`, and figures.
- `scripts/smoke_router.sh` removes and regenerates `data/derived/router_results.jsonl`
  and `data/derived/router_summary.json`.
- `scripts/smoke_category.sh` removes category smoke outputs and smoke figures.

Run smoke scripts from a clean worktree, a temporary branch, or after saving any
tracked results you do not want regenerated.

## Known Reproducibility Gaps

- `README.md` was previously empty; this guide now records setup and experiment
  commands.
- There is no `uv.lock` or `pyproject.toml`; reproducibility is based on the
  pinned `requirements.txt` plus Python 3.13.
- Full MBPP category results are not reproducible from tracked files alone,
  because `data/derived/mbpp_modes_category.json` is not tracked.
- BBH has tracked 1.5B and 7B raw logs. The script `scripts/full_run_bbh.sh`
  mentions 32B, but the tracked router config uses only 1.5B and 7B logs.
- Local `docs/theory/` exists but is untracked in the current worktree.
- Live Ollama and Codex outputs are not bit-for-bit reproducible unless model
  digests, service versions, prompts, seeds, and generated raw logs are retained.
