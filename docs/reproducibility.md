# Reproducibility

This is the canonical reproduction map for the unified repository. Historical
experiment summaries are tracked evidence bundles. New live-agent runs are not
bit-for-bit reproducible because model routing, service versions, and agent
decisions can change; for serious reruns, pin models, use fixed-step
evaluation, and preserve the generated run directory.

## Environment

```bash
uv sync --dev --frozen
uv run pytest -q
```

Optional dependency profiles:

- `autoresearch`: Torch/Torchvision for CIFAR-10 verification.
- `other-experiments`: EvalPlus, Transformers, and related dependencies for
  HumanEval+/MBPP+/BBH.
- `swebench`: SWE-bench and Docker.
- `analysis-ml`: heavier analysis dependencies such as scipy and embedding
  models.
- `all-experiments`: all experiment profiles.

Copy `.env.example` to `.env` only when live provider-backed runs are required.
Never commit `.env`.

## Safe Local Checks

These commands inspect or regenerate checked-in evidence without launching live
agents:

```bash
make check
```

Expanded form:

```bash
python scripts/build_repo_inventory.py --output docs/audits/repo-inventory.md
python scripts/build_knowledge_index.py --output docs/audits/knowledge-index.md
python scripts/build_paper_archive_manifest.py --output docs/audits/paper-archive-manifest.md
python scripts/build_experiment_manifest.py --output docs/audits/experiment-manifest.md
python scripts/build_command_manifest.py --output docs/audits/command-manifest.md
python scripts/validate_agent_readiness.py
python -m compileall -q scripts src autoresearch
uv run pytest tests -q
```

Additional local smoke checks:

```bash
uv run pytest tests/vao_runtime tests/autoresearch_reproduction -q
uv run agent-workflow demo --experiment-id readme_demo
uv run agent-workflow doctor
uv run agent-workflow --help
```

Use `docs/audits/command-manifest.md` before running a command outside this
section. It marks safe local checks separately from live local runs, cluster
jobs, and mixed CLI surfaces.

## AutoResearch Evidence

Canonical evidence:

```text
experiments/autoresearch-cifar10/starting-model-calibration/
experiments/autoresearch-cifar10/evaluation-protocol-and-compute-calibration/
experiments/autoresearch-cifar10/shared-memory-ablation/
experiments/autoresearch-cifar10/swarm-vs-independent-agents/
experiments/autoresearch-cifar10/three-worker-model-routing/
```

The runnable infrastructure lives under:

- `autoresearch/benchmark/cifar10/`: CIFAR-10 benchmark, workload templates,
  verifier wrapper, and source validation.
- `autoresearch/configs/`: active H=20 configs using `gpt_5_3_codex`,
  `gpt_5_4`, and `gpt_5_4_mini`.
- `autoresearch/prompts/`: model-generation and router prompts.
- `autoresearch/analysis/`: pilot, threshold, routing, and accounting modules.
- `autoresearch/scripts/`: plotting, artifact, Slurm, and campaign helpers.
- `src/vao/`: compatibility runtime used by the AutoResearch harness.

Regenerate compact paper-facing figures from the processed analysis JSON:

```bash
uv run python -m autoresearch.scripts.reproduce_main_figures_from_processed \
  --input experiments/autoresearch-cifar10/three-worker-model-routing/results/accounting/threeworker_final_analysis.json \
  --out-dir /tmp/how_to_pick_a_model_autoresearch
```

Render the workload/action catalog:

```bash
uv run python -m autoresearch.analysis.autoresearch_cifar10_mode_catalog \
  --out-dir /tmp/how_to_pick_a_model_autoresearch_catalog
```

Prepare CIFAR-10 data only when running the benchmark locally:

```bash
cd autoresearch
uv run python prepare.py
cd ..
```

Minimal local-stub smoke run:

```bash
uv sync --dev --extra autoresearch --frozen
uv run python -m autoresearch.analysis.autoresearch_cifar10_pilot \
  --config autoresearch/configs/autoresearch_cifar10_workload_pilot.yaml \
  --models autoresearch_local_stub \
  --workloads cnn_compact \
  --seeds 7001:1 \
  --steps 1 \
  --max-train-steps 2 \
  --output-root /tmp/how_to_pick_a_model_autoresearch_smoke
```

## Other Experiment Evidence

The HumanEval+, MBPP+, and BBH pipeline uses root-level `src/*.py`; each
experiment's configs, data, results, and launchers are co-located in its bundle.
Use `docs/audits/experiment-manifest.md` for a generated asset-level view before
citing a bundle as complete evidence.

Safe trace checks:

```bash
uv run python -m src.load_traces --config experiments/humaneval-plus/retry-allocation-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/mbpp-plus/two-model-retry-router/configs/router.yaml
uv run python -m src.load_traces --config experiments/bbh/family-and-subtask-router/configs/router_experiment_bbh.yaml
```

Expected tracked trace coverage:

- HumanEval+: 164 tasks for each of 1.5B, 7B, and 32B.
- MBPP+: 378 tasks for each of 1.5B, 7B, and 32B.
- BBH: 1,200 tasks for 1.5B and 7B; no tracked 32B log.

Offline regeneration examples:

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

## Live AutoResearch Runs

Full reruns require the `autoresearch` extra, authenticated model access, and
enough compute for CIFAR-10 verification. Use Claude Code only from a clean
clone or disposable worktree.

```bash
uv run agent-workflow single-long \
  --config configs/experiment.yaml \
  --time-budget 10 \
  --train-budget 120 \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_single_long

uv run agent-workflow parallel-shared \
  --config configs/agent_roster_example.yaml \
  --train-max-steps 1170 \
  --serialized-evaluator \
  --experiment-id smoke_custom_roster

uv run agent-workflow swarm --blackboard-dir /tmp/agent-workflow-blackboard
uv run agent-workflow swarm --run --config configs/experiment.yaml --time-budget 10 --train-budget 120 --n-agents 2
```

Use reviewer-grade settings when a run will support a claim:

- `--train-max-steps 1170` so the evaluator is fixed-step.
- `--serialized-evaluator` when multiple agents share a machine.
- A pinned Claude model in `configs/experiment.yaml`.
- A pre-registered `--target-val-bpb` for certified hitting time.
- A clean `--experiment-id` that names the experiment and date.

Agent runs write under `runs/` by default. Preserve at least `config.json`,
per-agent logs, `results/trajectory.jsonl`, `results/results.tsv`,
`results/training_runs.jsonl`, snapshots, and aggregate reports.

## Paper

The submitted artifact and source are under `paper/`. When TeX Live is
available, compile the active manuscript sources out of tree:

```bash
make paper-build
```

This builds `arxiv.tex` into `/tmp/how_to_pick_a_model_paper_build` by default
and leaves the Overleaf-compatible source tree clean.

The known manuscript/result mismatch is documented in
[`audits/manuscript-reproducibility.md`](audits/manuscript-reproducibility.md).

## Reproducibility Limits

- Live model output is not bit-for-bit reproducible without exact model
  digests, server versions, prompts, seeds, and service state.
- MBPP category routing, BBH routing, and the MBPP two-model router do not have
  complete checked-in result bundles.
- The verifier-guided DAG smoke is incomplete at 9/42 cheap-node records.
- Historical SWE-bench manifests retain their original absolute paths as
  provenance; those paths are not current launch instructions.
