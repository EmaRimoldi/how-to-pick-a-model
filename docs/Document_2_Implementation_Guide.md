# Implementation Guide for an AI Coding Agent

## Project: Verifiable Agentic Optimization for Open-Ended Query-Engine Editing

This guide is written for a coding agent with no prior project context. Your task is to create a new experimental repository implementing the research protocol described in the accompanying NeurIPS-style paper.

The goal is to study language-model agents that iteratively optimize a structured artifact under an objective verifier. The artifact is a Python file, `solution.py`, implementing a stateful in-memory query engine. At each step, the agent must output a probability distribution over six editing modes and produce one candidate edit for each mode. All six candidate edits are verified offline, but initially only the top-probability branch is exposed to the agent at the next step. This creates both an online trajectory and a complete counterfactual step-by-mode tensor.

The first post-training experiment trains an open-weight code model on routing records derived from the verifier: given a checkpoint, predict the productive intervention mode.

---

## 1. Existing Codebase Components to Reuse

Create a new repository from scratch, but reuse the existing benchmark components listed below. Copy them into the new repository with minimal changes first; wrap them rather than rewriting them unless the guide explicitly says otherwise.

### 1.1 Reuse directly

| Existing path | Reuse as | Rationale |
|---|---|---|
| `stateful_query_engine/open_ended/solution_template.py` | `benchmarks/stateful_query_engine/solution_template.py` | Baseline editable artifact for all open-ended runs. |
| `dynamic_benchmark.py` | `benchmarks/stateful_query_engine/dynamic_benchmark.py` | Dynamic loader and verifier entrypoint for `solution.py`. |
| `harness/verify_correctness.py` | `benchmarks/stateful_query_engine/harness/verify_correctness.py` | Exact output-equivalence verifier against the reference engine. |
| `harness/evaluate_perf.py` | `benchmarks/stateful_query_engine/harness/evaluate_perf.py` | Latency and memory measurement. |
| `score.py` | `benchmarks/stateful_query_engine/score.py` | Scalar loss computation from performance ratios. |
| `metadata/instance_config.json` | `benchmarks/stateful_query_engine/metadata/instance_config.json` | Workload profile definitions. |
| `open_ended/claude_patch_adapter.py` | `src/vao/agents/claude_code_adapter.py` | Starting point for Claude Code file-editing calls. |
| `open_ended/open_ended_orchestrator.py` | reference only | Do not keep the old orchestration as primary; use it to understand run directories, snapshots, and evaluation subprocesses. |

### 1.2 Rewrite or add

You must write new modules for:

- mode taxonomy and mode classification;
- mode-complete branch generation;
- isolated branch workspaces;
- strict agent output contracts;
- variant C(a) logging and visibility;
- optional C(b) feedback-use diagnostic;
- estimator computation;
- routing-dataset construction;
- LoRA/QLoRA training for the open-weight student;
- experiment configuration and reproducible run scripts.

Do not implement multi-agent systems in this project. The main protocol is single-agent only.

---

## 2. Repository Layout

Create the following directory structure.

```text
vao-query-optimization/
  README.md
  pyproject.toml
  requirements.txt
  configs/
    models.yaml
    profiles.yaml
    phase1_dev.yaml
    phase1_holdout.yaml
    feedback_use_cb.yaml
    routing_training.yaml
  benchmarks/
    stateful_query_engine/
      solution_template.py
      dynamic_benchmark.py
      score.py
      metadata/
        instance_config.json
      harness/
        verify_correctness.py
        evaluate_perf.py
        run_benchmark.py        # optional compatibility wrapper
  src/
    vao/
      __init__.py
      taxonomy.py
      schemas.py
      logging_utils.py
      workspaces.py
      verifier.py
      orchestrator.py
      visibility.py
      estimators.py
      records.py
      agents/
        __init__.py
        base.py
        claude_code_adapter.py
        openai_compatible_adapter.py
        local_stub_adapter.py
      training/
        build_routing_dataset.py
        train_routing_lora.py
        evaluate_student.py
      analysis/
        aggregate_runs.py
        compute_estimators.py
        make_tables.py
  scripts/
    run_phase1_dev.sh
    run_phase1_holdout.sh
    build_routing_dataset.sh
    train_routing_student.sh
    evaluate_posttrained_student.sh
  tests/
    test_taxonomy.py
    test_mode_classifier.py
    test_schema_validation.py
    test_branch_workspace.py
    test_verifier_wrapper.py
    test_estimators.py
  runs/
    .gitkeep
  artifacts/
    .gitkeep
```

---

## 3. Core Definitions to Implement

### 3.1 Modes

Implement the six primary modes exactly:

```python
MODES = [
    "layout",
    "indexing",
    "topk",
    "caching",
    "summaries",
    "micro",
]
```

Definitions:

- `layout`: changes the primary storage representation, e.g. list to dict or dict plus sorted key list.
- `indexing`: changes range-query access paths, usually sorted keys and `bisect_left` / `bisect_right`.
- `topk`: changes the `top_k()` algorithm, e.g. heap-based selection or sort-key repair.
- `caching`: adds or changes memoization of query results and invalidation on writes.
- `summaries`: adds maintained aggregation structures such as prefix sums, Fenwick trees, or buckets.
- `micro`: constant-factor changes that do not alter the main algorithmic mechanism.

Each edit must have one `primary_mode`. It may have `secondary_modes`, but the primary analysis uses only `primary_mode`.

### 3.2 Agent output contract

At every step, the agent must produce a strict JSON object before code patches are materialized.

```json
{
  "mode_probs": {
    "layout": 0.20,
    "indexing": 0.30,
    "topk": 0.10,
    "caching": 0.15,
    "summaries": 0.20,
    "micro": 0.05
  },
  "mode_ranking": ["indexing", "layout", "summaries", "caching", "topk", "micro"],
  "mode_rationales": {
    "layout": "One sentence only.",
    "indexing": "One sentence only.",
    "topk": "One sentence only.",
    "caching": "One sentence only.",
    "summaries": "One sentence only.",
    "micro": "One sentence only."
  }
}
```

Validation rules:

1. All six modes must appear exactly once.
2. Probabilities must be numeric.
3. Sum must be within `1e-6` of 1.0 after normalization.
4. Ranking must be a permutation of the six modes.
5. If the JSON is invalid, retry once. If still invalid, use `local_stub_adapter` and mark the step as `agent_contract_failed=true`.

### 3.3 Branch candidates

For every step `t` and every mode `m`, create one branch workspace:

```text
runs/<run_id>/steps/step_0007/branches/indexing/
  parent_solution.py
  proposed_solution.py
  patch.diff
  proposal.json
  verification.json
```

The parent solution for all six branches at a step must be identical.

---

## 4. Step-by-Step Implementation

### Step 1 — Initialize the repository

1. Create the repository layout shown above.
2. Add `pyproject.toml` with package name `vao-query-optimization`.
3. Add dependencies to `requirements.txt`:
   - `pydantic>=2`
   - `pyyaml`
   - `numpy`
   - `pandas`
   - `scipy`
   - `tqdm`
   - `rich`
   - `datasets`
   - `transformers`
   - `accelerate`
   - `peft`
   - `trl`
   - `bitsandbytes` if GPU setup supports it
4. Copy the reusable benchmark files into `benchmarks/stateful_query_engine/`.
5. Run the existing dynamic benchmark once on `solution_template.py` to confirm baseline evaluation works.

Expected command:

```bash
python -m benchmarks.stateful_query_engine.dynamic_benchmark \
  --solution benchmarks/stateful_query_engine/solution_template.py \
  --profile paper_development \
  --out artifacts/baseline_eval.json
```

If the existing `dynamic_benchmark.py` does not expose this exact CLI, write a thin wrapper in `src/vao/verifier.py` and preserve the underlying verifier logic.

### Step 2 — Implement schemas

Create `src/vao/schemas.py` with Pydantic models:

- `ModeDistribution`
- `CandidateProposal`
- `BranchEvaluation`
- `StepRecord`
- `RunManifest`
- `RoutingRecord`

Minimum `StepRecord` fields:

```python
class StepRecord(BaseModel):
    run_id: str
    profile_id: str
    model_id: str
    step: int
    parent_solution_hash: str
    mode_probs: dict[str, float]
    mode_ranking: list[str]
    selected_mode: str
    selected_branch: str
    visibility_regime: Literal["top1_only", "all_branches"]
    branches: list[BranchEvaluation]
    residual_steps: int
    residual_wall_seconds: float | None
    agent_cost_usd: float | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: str
```

### Step 3 — Implement taxonomy and classifier

Create `src/vao/taxonomy.py`.

Implement:

```python
def validate_mode(mode: str) -> str: ...
def normalize_mode_probs(probs: dict[str, float]) -> dict[str, float]: ...
def classify_edit_mode(pre_source: str, post_source: str) -> tuple[str, list[str], dict]: ...
```

Classifier rules:

- `caching` if `_cache`, `cache`, or `.clear()` invalidation appears in added lines.
- `summaries` if `_prefix`, `_fenwick`, `_bit`, `_bucket`, `_sum_tree`, or maintained aggregate arrays appear.
- `topk` if the dominant changes are inside `top_k`, or `heapq` is newly used for top-k selection.
- `indexing` if `bisect_left`, `bisect_right`, `insort`, `_keys`, or `_range_bounds` are introduced or changed.
- `layout` if `__init__`, `put`, `delete`, or `get` change the primary representation, especially `_items` to `_values` / dict.
- `micro` if none of the structural rules fire and changes are local expression rewrites.

Return both `primary_mode` and `secondary_modes`. Tests must cover compound `layout + indexing` edits.

### Step 4 — Implement verifier wrapper

Create `src/vao/verifier.py`.

Responsibilities:

1. Copy a candidate `proposed_solution.py` to an isolated temp directory.
2. Call the reused dynamic benchmark.
3. Return:
   - `correctness`
   - `latent_loss`
   - `family_losses`
   - `first_divergence`
   - `median_p95_latency_ns`
   - `median_peak_memory_bytes`
   - `raw_verifier_path`
4. Apply a timeout.
5. Never mutate the parent workspace.

Function interface:

```python
def evaluate_solution(
    solution_path: Path,
    profile_id: str,
    timeout_seconds: int,
    out_path: Path,
) -> BranchEvaluation: ...
```

### Step 5 — Implement branch workspaces

Create `src/vao/workspaces.py`.

Functions:

```python
def create_run_dir(root: Path, config: dict) -> Path: ...
def init_workspace(run_dir: Path, template_path: Path) -> Path: ...
def create_step_branches(run_dir: Path, step: int, parent_solution: Path, modes: list[str]) -> dict[str, Path]: ...
def promote_branch_to_parent(branch_solution: Path, workspace_solution: Path) -> None: ...
def sha256_file(path: Path) -> str: ...
def write_diff(pre: str, post: str, out_path: Path) -> None: ...
```

Validation: all branches in a step must begin from the same parent hash.

### Step 6 — Implement agent adapters

Create `src/vao/agents/base.py`:

```python
class AgentAdapter(Protocol):
    def propose_mode_distribution(self, state: AgentState) -> ModeDistribution: ...
    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal: ...
```

Create three adapters:

1. `claude_code_adapter.py`
   - Use Claude Code or existing subprocess behavior.
   - It must edit only the branch's `proposed_solution.py`.
   - Prompt must constrain the mode.

2. `openai_compatible_adapter.py`
   - For Qwen served through vLLM or SGLang.
   - Generate full file content or a unified diff.
   - Apply patch deterministically.

3. `local_stub_adapter.py`
   - Deterministic fallback for tests.
   - Can copy the parent unchanged or apply simple known edits.

### Step 7 — Implement orchestrator

Create `src/vao/orchestrator.py`.

Main command:

```bash
python -m vao.orchestrator --config configs/phase1_dev.yaml
```

Orchestrator algorithm:

1. Load config.
2. Create run directory.
3. Copy `solution_template.py` to `workspace/solution.py`.
4. Evaluate baseline parent solution and store `baseline_verification.json`.
5. For each step `t`:
   1. Build `AgentState` from visible history.
   2. Ask agent for `mode_probs` and `mode_ranking`.
   3. Create six branch workspaces from the same parent solution.
   4. For each mode:
      - ask agent to produce one edit constrained to that mode;
      - validate source using the benchmark safety gate;
      - classify diff to get `inferred_mode`;
      - evaluate branch with verifier;
      - write branch artifacts.
   5. Select `selected_mode = argmax(mode_probs)`.
   6. Promote selected branch to `workspace/solution.py`.
   7. Write `step_record.json` and append to `evaluations.jsonl`.
   8. Update visible history according to regime:
      - `top1_only`: only selected branch feedback visible;
      - `all_branches`: all branch feedback visible.
6. Write final `run_summary.json`.

### Step 8 — Implement visibility regimes

Create `src/vao/visibility.py`.

Functions:

```python
def build_visible_history(records: list[StepRecord], regime: str) -> list[dict]: ...
def summarize_history_for_prompt(records: list[StepRecord], max_rows: int) -> str: ...
```

Regimes:

- `top1_only`: C(a), main protocol.
- `all_branches`: C(b), feedback-use diagnostic.

### Step 9 — Implement estimators

Create `src/vao/estimators.py`.

Implement:

```python
def gain(parent_loss: float, branch_loss: float, correct: bool, incorrect_penalty: float) -> float: ...
def productive_mode_proxy(gains: dict[str, float], fallback: str = "uniform") -> dict[str, float]: ...
def routing_regret(gains: dict[str, float], selected_mode: str) -> float: ...
def jsd(p: dict[str, float], q: dict[str, float]) -> float: ...
def routing_mismatch_jSd(step: StepRecord) -> float: ...
def runtime_phi(records: list[StepRecord]) -> pd.DataFrame: ...
def endpoint_best_loss(records: list[StepRecord]) -> float: ...
def success_above_threshold(records: list[StepRecord], threshold: float) -> bool: ...
def cost_per_step(records: list[StepRecord]) -> dict: ...
def alignment_gain(pre: dict[str,float], post: dict[str,float], pstar: dict[str,float]) -> float: ...
```

Primary estimators:

- endpoint: best verified loss within budget;
- endpoint: success above threshold;
- routing: mean regret;
- secondary routing: mean JSD;
- runtime competence: mean gain by mode;
- feedback use: alignment gain in `all_branches` diagnostic.

### Step 10 — Implement analysis scripts

Create:

- `src/vao/analysis/aggregate_runs.py`
- `src/vao/analysis/compute_estimators.py`
- `src/vao/analysis/make_tables.py`

Expected command:

```bash
python -m vao.analysis.compute_estimators \
  --runs runs/phase1_dev \
  --out artifacts/phase1_dev_estimators.csv
```

Output columns:

```text
run_id,profile_id,model_id,visibility_regime,best_loss,success,mean_routing_regret,mean_jsd,mean_cost_wall,mean_cost_tokens,invalid_rate,mean_gain_layout,mean_gain_indexing,mean_gain_topk,mean_gain_caching,mean_gain_summaries,mean_gain_micro
```

---

## 5. Configuration Files

### 5.1 `configs/models.yaml`

```yaml
models:
  strong_claude:
    adapter: claude_code
    model_id: claude-opus-current
    temperature: 0.3
    timeout_seconds: 180
  mid_claude:
    adapter: claude_code
    model_id: claude-haiku-current
    temperature: 0.3
    timeout_seconds: 180
  weak_qwen:
    adapter: openai_compatible
    model_id: Qwen/Qwen3-Coder-Next
    base_url: http://localhost:8000/v1
    temperature: 0.3
    timeout_seconds: 180
```

Use exact model identifiers available in the execution environment. Do not hard-code vendor-specific names outside config.

### 5.2 `configs/phase1_dev.yaml`

```yaml
experiment:
  name: phase1_dev
  visibility_regime: top1_only
  modes: [layout, indexing, topk, caching, summaries, micro]
  steps: 20
  wall_budget_seconds: 7200
  branch_timeout_seconds: 240
  incorrect_penalty: -1.0
  productive_proxy_fallback: uniform
  history_policy: full_visible_history

benchmark:
  template_path: benchmarks/stateful_query_engine/solution_template.py
  profiles: [paper_development, search_hard_90min, memory_holdout]

models:
  include: [strong_claude, mid_claude, weak_qwen]

output:
  root: runs/phase1_dev
```

### 5.3 `configs/phase1_holdout.yaml`

```yaml
experiment:
  name: phase1_holdout
  visibility_regime: top1_only
  modes: [layout, indexing, topk, caching, summaries, micro]
  steps: 40
  wall_budget_seconds: 14400
  branch_timeout_seconds: 240
  incorrect_penalty: -1.0
  productive_proxy_fallback: uniform
  history_policy: full_visible_history

benchmark:
  template_path: benchmarks/stateful_query_engine/solution_template.py
  profiles: [holdout_balanced_unseen, holdout_distribution_shift]

models:
  include: [strong_claude, mid_claude, weak_qwen]

output:
  root: runs/phase1_holdout
```

Replace placeholder holdout names with actual profile IDs from `instance_config.json`.

### 5.4 `configs/feedback_use_cb.yaml`

```yaml
experiment:
  name: feedback_use_cb
  visibility_regime: all_branches
  modes: [layout, indexing, topk, caching, summaries, micro]
  checkpoint_source: runs/phase1_dev
  checkpoints_per_model: 50
  ask_post_feedback_distribution: true
  branch_timeout_seconds: 240

models:
  include: [strong_claude, mid_claude, weak_qwen]

output:
  root: runs/feedback_use_cb
```

### 5.5 `configs/routing_training.yaml`

```yaml
training:
  base_model: Qwen/Qwen3-Coder-Next
  method: qlora
  target: soft_productive_mode_distribution
  train_records: artifacts/routing_train.jsonl
  eval_records: artifacts/routing_dev.jsonl
  output_dir: artifacts/qwen_routing_lora
  max_seq_length: 32768
  learning_rate: 0.00003
  lora_rank: 16
  lora_alpha: 32
  batch_size: 1
  gradient_accumulation_steps: 16
  epochs: 2
  seed: 1234
```

---

## 6. Experiments to Implement

### Experiment E1 — Instrumentation Sanity

Purpose: verify that the branch protocol works before expensive runs.

Steps:

1. Run `local_stub_adapter` for 2 steps on one small profile.
2. Confirm each step has exactly six branches.
3. Confirm all branches share the same parent hash.
4. Confirm every branch has `proposal.json`, `patch.diff`, `verification.json`.
5. Confirm `mode_probs` sums to 1.
6. Confirm `selected_mode` equals argmax of `mode_probs`.
7. Confirm `workspace/solution.py` equals the selected branch after promotion.
8. Run `pytest`.

Command:

```bash
python -m vao.orchestrator --config configs/phase1_dev.yaml \
  --models local_stub --profiles paper_development --steps 2
pytest -q
```

Expected outputs:

```text
runs/phase1_dev/<run_id>/run_manifest.json
runs/phase1_dev/<run_id>/evaluations.jsonl
runs/phase1_dev/<run_id>/steps/step_0000/branches/<mode>/verification.json
```

### Experiment E2 — Endpoint Backbone Comparison

Purpose: compare strong, mid, and weak backbones on identical profiles and budgets.

Steps:

1. Start Qwen serving endpoint if using Qwen.
2. Run all three backbones on the three dev profiles.
3. Run all three backbones on the two holdout profiles.
4. Aggregate endpoint metrics.
5. Produce table: model by profile, best loss, success threshold, invalid rate, cost.

Commands:

```bash
bash scripts/run_phase1_dev.sh
bash scripts/run_phase1_holdout.sh
python -m vao.analysis.compute_estimators --runs runs/phase1_dev --out artifacts/phase1_dev_estimators.csv
python -m vao.analysis.compute_estimators --runs runs/phase1_holdout --out artifacts/phase1_holdout_estimators.csv
python -m vao.analysis.make_tables --estimators artifacts/phase1_holdout_estimators.csv --out artifacts/tables_endpoint.md
```

### Experiment E3 — Routing Diagnostics

Purpose: estimate routing mismatch `epsilon`.

Steps:

1. For every step record, compute gains for six branches.
2. Compute soft productive-mode proxy.
3. Compute routing regret using selected top-1 mode.
4. Compute JSD between `mode_probs` and productive-mode proxy.
5. Aggregate by model, profile, step bucket, and mode.
6. Output CSV and plots if desired. Keep plots black and white.

Command:

```bash
python -m vao.analysis.compute_estimators \
  --runs runs/phase1_holdout \
  --metrics routing \
  --out artifacts/routing_diagnostics.csv
```

### Experiment E4 — Within-Mode Competence

Purpose: estimate runtime and controlled versions of `phi`.

Runtime version:

1. Use existing branch tensors.
2. For each mode, average verified gains across steps and runs.
3. Report by model and mode.

Controlled version:

1. Sample checkpoints from dev runs.
2. For each checkpoint and each mode, ask every backbone to generate a mode-constrained edit from the same parent artifact.
3. Verify each edit.
4. Compute relative gain against strong teacher or model mean.

Command:

```bash
python -m vao.orchestrator \
  --config configs/phase1_dev.yaml \
  --controlled_checkpoints artifacts/shared_checkpoints.jsonl \
  --mode_controlled true \
  --out runs/controlled_phi

python -m vao.analysis.compute_estimators \
  --runs runs/controlled_phi \
  --metrics phi_controlled \
  --out artifacts/phi_controlled.csv
```

### Experiment E5 — Feedback-Use Diagnostic

Purpose: estimate `G`, the alignment gain after feedback.

Steps:

1. Sample checkpoints from Phase 1 dev runs.
2. Ask model for pre-feedback `mode_probs`.
3. Generate one edit per mode and verify all branches.
4. Expose all branch results to the model.
5. Ask model for post-feedback `mode_probs`.
6. Compute productive-mode proxy from branch gains.
7. Compute `JSD(pre, pstar) - JSD(post, pstar)`.
8. Aggregate by model and profile.

Command:

```bash
python -m vao.orchestrator --config configs/feedback_use_cb.yaml
python -m vao.analysis.compute_estimators \
  --runs runs/feedback_use_cb \
  --metrics feedback_use \
  --out artifacts/feedback_use_alignment.csv
```

### Experiment E6 — Routing Post-Training

Purpose: train the open-weight student to predict productive modes.

Dataset construction:

1. Read development step records.
2. For each step, build input from checkpoint summary and visible history.
3. Compute productive-mode proxy from verified gains.
4. Store JSONL record with target distribution.
5. Split train/dev by profile and run ID.

Command:

```bash
python -m vao.training.build_routing_dataset \
  --runs runs/phase1_dev \
  --target soft_productive_mode_distribution \
  --train_out artifacts/routing_train.jsonl \
  --dev_out artifacts/routing_dev.jsonl
```

Training:

```bash
python -m vao.training.train_routing_lora --config configs/routing_training.yaml
```

Evaluation:

```bash
python -m vao.training.evaluate_student \
  --adapter artifacts/qwen_routing_lora \
  --config configs/phase1_holdout.yaml \
  --out runs/qwen_routing_lora_holdout

python -m vao.analysis.compute_estimators \
  --runs runs/qwen_routing_lora_holdout \
  --out artifacts/qwen_routing_lora_holdout_estimators.csv
```

Controls:

1. No fine-tuning.
2. Random target labels.
3. Generic trajectory imitation with matched number of records.
4. Teacher-distribution distillation if teacher distributions are available.

### Experiment E7 — Ablations

Implement these only after E1-E6 pass.

Ablations:

1. Hard vs soft productive-mode targets.
2. Primary mode only vs primary plus secondary modes.
3. Top-1 visibility vs all-branches visibility.
4. Full history vs compressed history.
5. Fixed K=6 vs adaptive K.
6. Incorrect gain penalty vs correctness gating.

Each ablation must produce its own config file and output directory.

---

## 7. Logging Conventions

### 7.1 Required run files

Every run directory must contain:

```text
run_manifest.json
baseline_verification.json
evaluations.jsonl
run_summary.json
config_resolved.yaml
```

### 7.2 Required branch files

Every branch directory must contain:

```text
parent_solution.py
proposed_solution.py
patch.diff
proposal.json
verification.json
```

### 7.3 JSONL rule

Each line of `evaluations.jsonl` is exactly one `StepRecord`. Do not log partial step records. If a run crashes mid-step, write a `crash_report.json` in the step directory but do not append an invalid line.

### 7.4 Hashes

Log SHA-256 hashes for:

- parent solution;
- each proposed solution;
- agent prompt;
- model raw output;
- verifier output.

---

## 8. Testing and Validation

### Before any model run

Run:

```bash
pytest -q
python -m vao.verifier --smoke_test
```

Must pass:

- baseline loads;
- verifier returns correctness and loss;
- mode classifier handles known synthetic diffs;
- schemas reject invalid mode probabilities;
- branch workspaces have identical parent hashes.

### Before expensive Claude/Qwen runs

Run a two-step local stub experiment. Validate all artifacts manually.

### Before post-training

Confirm:

- routing dataset contains no holdout profiles;
- targets are computed only from verifier outputs;
- all records have valid `mode_probs`, `target_mode_dist`, and `state_summary`;
- no branch result that should be hidden under C(a) is included in the online prompt state.

### Before reporting numbers

Confirm:

- all compared models used the same profiles and budgets;
- all model calls used the same scaffold;
- failed/invalid generations are included in metrics;
- exact model identifiers are recorded;
- random seeds are recorded;
- estimator code is version-pinned.

---

## 9. Expected Final Artifacts

After all Phase 1 experiments:

```text
artifacts/
  phase1_dev_estimators.csv
  phase1_holdout_estimators.csv
  routing_diagnostics.csv
  phi_runtime.csv
  phi_controlled.csv
  feedback_use_alignment.csv
  routing_train.jsonl
  routing_dev.jsonl
  qwen_routing_lora/
  qwen_routing_lora_holdout_estimators.csv
  tables_endpoint.md
  tables_diagnostics.md
```

The paper should be able to draw directly from these artifacts.

---

## 10. Non-Negotiable Rules

1. Do not change the verifier while comparing models.
2. Do not change mode definitions after holdout runs begin.
3. Do not tune prompts on holdout profiles.
4. Do not expose offline branch results to the model in the C(a) main protocol.
5. Do not omit failed or incorrect branches from diagnostic calculations.
6. Do not post-train closed-source models.
7. Do not merge multi-agent features into the main experiments.
8. Do not report endpoint results without diagnostic estimators.
9. Do not report post-training gains without matched no-training and generic-training controls.

---

## 11. Minimal Definition of Done

The project is ready for first scientific analysis when:

- the orchestrator can run one complete C(a) run with six branches per step;
- the verifier logs correctness and loss for every branch;
- `q_t(m)` is logged and validated at every step;
- productive-mode proxies and routing regret are computed automatically;
- endpoint metrics are computed automatically;
- routing records can be exported to JSONL;
- the open-weight student can be fine-tuned on routing records;
- the post-trained student can be evaluated on held-out profiles without changing the scaffold.
