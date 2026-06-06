# SWE-bench Distribution-Aware Orchestration Experiments

This folder is for the first SWE-bench orchestration experiment.

Architecture boundary:

- Codex is used only as an offline meta-designer to produce a frozen orchestration JSON.
- Runtime orchestration execution must not use Codex, Claude, or proprietary hosted workers.
- `vao.swebench_orchestration.executor` runs the frozen spec with open-source models served from external GPU OpenAI-compatible endpoints and emits patch-generation-only traces/predictions.

## 1. Download a leakage-safe Verified slice

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.download \
  --dataset-name princeton-nlp/SWE-Bench_Verified \
  --split test \
  --limit 8 \
  --output-dir experiments/swebench_orchestration/data/smoke
```

This creates:

- `data/smoke/instances_public.jsonl`: prompt-safe instance records, no gold patches.
- `data/smoke/instances_private_metadata.jsonl`: private metadata for bookkeeping.
- `data/smoke/download_manifest.json`: dataset/source manifest.

## 2. Render the meta-designer prompt

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.prompt \
  --config configs/swebench_orchestration_smoke.yaml
```

This writes:

- `smoke/meta_design/meta_designer_prompt.md`
- `smoke/meta_design/orchestration_design_schema.json`

To invoke local Codex CLI directly:

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.prompt \
  --config configs/swebench_orchestration_smoke.yaml \
  --invoke-codex
```

For the full Verified slice, first download without a limit into
`experiments/swebench_orchestration/data/verified_full`, then run:

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.prompt \
  --config configs/swebench_orchestration_smoke.yaml \
  --instances experiments/swebench_orchestration/data/verified_full/instances_public.jsonl \
  --output-dir experiments/swebench_orchestration/verified_full/meta_design \
  --invoke-codex
```

## 3. Serve Open-Source Workers

The runtime worker config is `configs/swebench_open_source_workers.yaml`.
It assumes OpenAI-compatible endpoints:

- `qwen_coder_7b`: `Qwen/Qwen2.5-Coder-7B-Instruct` at `http://localhost:8000/v1`
- `qwen_coder_14b`: `Qwen/Qwen2.5-Coder-14B-Instruct` at `http://localhost:8001/v1`
- `qwen_coder_32b`: `Qwen/Qwen2.5-Coder-32B-Instruct` at `http://localhost:8002/v1`

The exact serving command is intentionally not fixed here; use vLLM or SGLang on
the A100 node and keep the endpoint URLs stable.

## 4. Run the Executor Pilot

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.executor \
  --config configs/swebench_orchestration_pilot.yaml
```

This writes:

- `open_source_pilot/traces.jsonl`
- `open_source_pilot/predictions.jsonl`
- `open_source_pilot/executor_manifest.json`

Use `--dry-run` to validate config, schema, and output shape without making GPU
endpoint calls. The executor currently does not materialize repositories, run
tests, or invoke the official verifier; it logs that limitation explicitly and
emits unverified patch candidates for the downstream SWE-bench harness.

## 5. Log orchestration runs

Every generated orchestration run should emit JSONL trace rows matching
`vao.swebench_orchestration.schemas.TraceStep`.  The required fields are:

- `run_id`, `orchestration_id`, `evidence_level`
- `instance_id`, `repo`, `mode`, `split`
- `step`, `phase`, `agent_id`, `model_id`
- token, API, wall-clock, test, and verifier-call costs
- `patch_id`, `verified`, `used_in_verified_path`

## 6. Evaluate patches

When an orchestration produces a patch, write a SWE-bench predictions JSONL:

```json
{"instance_id": "...", "model_name_or_path": "orchestration_id", "model_patch": "...unified diff..."}
```

Then prepare or execute the official harness command:

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.evaluate \
  --dataset-name princeton-nlp/SWE-Bench_Verified \
  --split test \
  --predictions experiments/swebench_orchestration/smoke/predictions.jsonl \
  --run-id swebench_orchestration_smoke
```

Add `--execute` only after the official `swebench` harness and Docker
environment are installed.

## 7. Analyze traces

```bash
PYTHONPATH=src:. ./.venv/bin/python -m vao.swebench_orchestration.analyze \
  --traces experiments/swebench_orchestration/smoke/traces.jsonl \
  --orchestration-design experiments/swebench_orchestration/smoke/meta_design/orchestration_design.json \
  --output experiments/swebench_orchestration/smoke/analysis/report.json
```

The report contains run summaries, mode-conditioned certified resource,
frontier ratios, difficulty-normalized imbalance, and wasted-effort diagnostics.
