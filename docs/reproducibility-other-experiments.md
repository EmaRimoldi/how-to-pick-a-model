# Reproducibility: HumanEval+, MBPP+, BBH, and SWE-bench

## Environment

```bash
uv sync --dev --extra other-experiments --frozen
uv run python -m compileall -q src experiments
```

Live worker runs require Ollama and the model named by the selected config.
Router runs using `codex_cli` require an authenticated `codex` binary and
`ROUTER_MODEL`. SWE-bench execution additionally requires the `swebench` extra,
Docker or Modal for official evaluation, and GPU/Slurm resources for the
provided vLLM launcher.

## Safe Read-Only Checks

```bash
uv run python -m src.load_traces --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/mbpp-plus/two-model-retry-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/bbh/family-and-subtask-router/configs/router_experiment_bbh.yaml
```

Expected tracked trace coverage:

- HumanEval+: 164 tasks for each of 1.5B, 7B, and 32B.
- MBPP+: 378 tasks for each of 1.5B, 7B, and 32B.
- BBH: 1,200 tasks for 1.5B and 7B; no tracked 32B log.

## Result Matrix

| Bundle | Offline evidence | What a live rerun needs |
| --- | --- | --- |
| `humaneval-plus/qwen-model-size-frontier` | complete worker logs and processed frontier files | Ollama with Qwen2.5-Coder 1.5B/7B/32B |
| `humaneval-plus/retry-allocation-router` | folds, router JSONL, summary | Codex CLI/API only to regenerate router decisions |
| `humaneval-plus/strategy-by-difficulty-grid` | complete dated run with raw shards, snapshots, summaries, logs, figures | cluster/Slurm plus configured workers and router |
| `humaneval-plus/llm-router-context-search` | validation selection and held-out test evaluation | cluster/Slurm plus configured LLMs |
| `humaneval-plus/verifier-guided-dag-induction-smoke` | implementation and incomplete smoke traces | 33 missing cheap-node records before full diagnostics |
| `mbpp-plus/qwen-model-size-frontier` | complete three-model worker logs and modes | Ollama with Qwen2.5-Coder models |
| `mbpp-plus/two-model-retry-router` | config and folds only | rerun router, estimator, and plotter |
| `mbpp-plus/category-router-smoke` | configs and historical smoke figures | produce full category labels, then router outputs |
| `bbh/qwen-model-size-frontier` | 1.5B/7B logs and mode files | missing 32B worker run for the configured three-model frontier |
| `bbh/family-and-subtask-router` | configs and launchers only | rerun router, estimator, and plotter |
| `swebench-verified/neutral-100-meta-design-scaffold` | prompt-safe input/config scaffold | meta-design call, executor, and official verifier |
| `swebench-verified/open-source-orchestration-scaffold` | prompt-safe data and orchestration configs | design artifact and GPU-backed workers |
| `swebench-verified/open-source-meta-loop-2026-06-07` | historical evaluations and failure analysis | archived evidence is inspectable; a new run uses the shared runtime |

## Offline Regeneration

HumanEval+ frontier and router figures:

```bash
uv run python -m src.estimate --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
uv run python -m src.plot --config experiments/humaneval-plus/qwen-model-size-frontier/configs/experiment.yaml
uv run python -m src.estimate_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.plot_router --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
```

SWE-bench unit tests and neutral meta-design prompt generation:

```bash
export PYTHONPATH="$PWD/src:$PWD/experiments/swebench-verified/shared-runtime/src:$PWD"
uv run pytest experiments/swebench-verified/shared-runtime/tests -q
uv run python -m vao.swebench_orchestration.prompt \
  --config experiments/swebench-verified/neutral-100-meta-design-scaffold/configs/swebench_meta_design_neutral.yaml \
  --instances experiments/swebench-verified/neutral-100-meta-design-scaffold/data/verified_100/instances_public.jsonl \
  --output-dir /tmp/how-to-pick-a-model-swebench-meta-design
```

Do not add `--invoke-codex`, execute official verification, or run the Slurm
launchers during a read-only audit.

## Reproducibility Limits

- Live model output is not bit-for-bit reproducible without exact model
  digests, server versions, prompts, seeds, and service state.
- MBPP category routing, BBH routing, and the MBPP two-model router do not have
  complete checked-in result bundles.
- The verifier-guided DAG smoke is incomplete at 9/42 cheap-node records.
- Historical SWE-bench manifests retain their original absolute paths as
  provenance; those paths are not current launch instructions.
