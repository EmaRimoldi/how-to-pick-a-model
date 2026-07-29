# Single-50 SWE-bench Meta-Orchestration Report

Date: 2026-06-07

## Question

We tested whether a fresh single orchestration can run on a wider SWE-bench pool, produce patches, expose the four optimization terms, and let the Meta-Orchestrator update the orchestration from observed failures.

This is the first real 50-instance pass of that loop. It is a successful pipeline test, but not yet a successful solver.

## Clarifications

`failure bundle troppo povero` means that the Meta-Orchestrator receives too little failure evidence to infer a useful update. A useful bundle needs public problem text, localizer/router notes, selected repo snippets, patch text or empty-patch reason, local apply-check status, verifier output, and mode/cost summaries.

`public_literal_repair_enabled` is not itself an orchestration born from the first Meta-Orchestrator design. It is a runtime primitive exposed to the executor. In this 50-instance experiment it was disabled in the fresh run, then enabled only after the Meta-Orchestrator explicitly selected it in the update. Scientifically, it should be counted as a Meta-Orchestrator-selected primitive only from the updated run onward.

## Setup

Fresh pool:

- 50 SWE-bench Verified public instances.
- Stratified modes: `repo_family`, `dependency_config`, `semantic_api`, `test_localizable`, `numeric_symbolic`, `multi_file`.
- Dataset file: `experiments/swebench_orchestration/data/verified_50_fresh/instances_public.jsonl`

Fresh single orchestration:

- `design_id`: `e2_50_stratified_swe_verified_distaware_20260607_01`
- `orchestration_id`: `swev_e250_routed_onepass_escalator_20260607_b4c1`
- type: `hierarchical_routed`
- name: `Stratified One-Patch Escalator`
- components: controller/router, localizer, primary patcher, reviewer, tester, fallback.

Initial config:

- `public_literal_repair_enabled: false`
- `max_calls_per_component: 1`
- `patch_repair_attempts: 1`

## Implementation Changes

The executor now:

- writes predictions before traces;
- fail-opens per instance, so one broken instance does not kill the 50-instance batch;
- runs local `git apply --check --whitespace=nowarn -` on non-empty patches;
- can retry invalid patch formatting before final selection;
- can expose `public_literal_repair` as a policy-gated deterministic primitive;
- records richer trace events and compact fallback traces if disk or quota pressure appears.

The Slurm pilot now:

- captures executor stdout/stderr explicitly;
- copies those logs back to the run directory;
- tails executor logs on failure.

The Codex CLI adapter now:

- passes long Meta-Orchestrator prompts through stdin, avoiding `Argument list too long`.

The Modal evaluation wrapper now:

- validates predictions;
- tracks empty patches;
- collects per-instance logs using the actual `model_name_or_path` that produced each patch.

Verification:

- `tests/test_swebench_orchestration.py`: `26 passed`.

## Run 1: Fresh Orchestration

Run:

- `single50_fresh_20260607_110055`
- Slurm job: `15570504`
- node: `node3620`

Executor outcome:

- predictions: 50
- non-empty patches: 0
- empty patches: 50
- trace rows: 459
- input tokens: 2,378,740
- output tokens: 51,309
- model wall seconds: 1,510.79

Modal/SWE-bench outcome:

- run: `single50_fresh_20260607_110055_modal_eval`
- official evaluator completed, but printed `No instances to run`
- reason: all 50 patches were empty

Interpretation:

The orchestration gathered useful context and often localized plausible files, but the patching contract failed: patcher/fallback mostly abstained or produced invalid candidates that were discarded. The verifier could not evaluate semantic correctness because no candidate patch survived.

## Meta-Orchestrator Update

Update artifact:

- `swebench/runs/single50_fresh_20260607_110055/meta_update/meta_update.json`

Update id:

- `meta_update_single50_fresh_20260607_empty_patch_contract_fix_v1`

Config changes chosen by the Meta-Orchestrator:

```yaml
max_calls_per_component: 2
patch_repair_attempts: 2
public_literal_repair_enabled: true
```

Main diagnosis:

- all 50 final predictions were empty;
- localizer/router evidence was not being converted into patches;
- component call budget was too tight;
- invalid diff repair needed to be explicit;
- deterministic public-literal repair should be tried as a leakage-safe primitive when public issue text contains explicit old/new literals.

## Run 2: Updated Orchestration

Run:

- `single50_updated_20260607_112356`
- Slurm job: `15571090`
- node: `node3620`

Executor outcome:

- predictions: 50
- non-empty patches: 8
- empty patches: 42
- trace rows: 720
- input tokens: 3,912,013
- output tokens: 105,147
- model wall seconds: 3,685.61

Patch sources:

- `public_literal_repair`: 5 patches
- `Qwen/Qwen2.5-Coder-7B-Instruct`: 3 patches

Local apply-check:

- passed: 8
- failed: 80
- skipped: 45

Non-empty patches by declared mode:

- `dependency_config`: 2
- `multi_file`: 2
- `numeric_symbolic`: 1
- `repo_family`: 1
- `semantic_api`: 1
- `test_localizable`: 1

Modal/SWE-bench outcome:

- run: `single50_updated_20260607_112356_modal_eval`
- submitted instances: 50
- completed non-empty candidates: 8
- empty patch instances: 42
- resolved instances: 0
- unresolved instances: 7
- error instances: 1

Completed candidate ids:

- `astropy__astropy-13033`
- `astropy__astropy-7166`
- `matplotlib__matplotlib-24026`
- `pydata__xarray-2905`
- `pydata__xarray-4966`
- `pydata__xarray-6992`
- `pytest-dev__pytest-10356`
- `scikit-learn__scikit-learn-10908`

The `matplotlib__matplotlib-24026` candidate had a Modal sandbox error, not a patch-apply failure. The other 7 completed candidates were unresolved. None of the 8 showed `Patch Apply Failed` in the collected per-instance logs.

## Four-Term Diagnosis

### 1. Solution-Generation Cost

The update increased candidate production but also increased cost:

- run 1: 2,430,049 total tokens, 1,510.79 model wall seconds, 0 candidate patches;
- run 2: 4,017,160 total tokens, 3,685.61 model wall seconds, 8 candidate patches.

This is not yet economical. The next optimization must reduce wasted calls on instances where patchers still return empty or invalid diffs.

### 2. Retries To Verified Success

Stopping time was not reached on the 50-instance pool:

- run 1: no verifiable candidates;
- run 2: 8 verifiable candidates, 0 verified successes.

So the loop improved from "no candidate" to "candidate generation", but not to verified resolution.

### 3. Information Loss

The first run lost information between localization and patching: public problem text and repository snippets were available, but not turned into a concrete diff.

The updated run reduced that loss for literal-like cases, but introduced a new risk: `public_literal_repair` can overfit superficial old/new literals and produce semantically wrong source edits. This means the primitive needs stricter gating and attribution.

### 4. Mode/Allocation Mismatch

The updated orchestration produced candidates across multiple modes, which is good. But the success rate remained 0, meaning allocation is still mismatched:

- many instances still consume controller/localizer/reviewer/fallback calls and end empty;
- literal repair can be cheap, but should not be applied just because two public literals exist;
- semantic/API and multi-file modes need stronger local test or targeted reproduction signals before Modal.

## Scientific Takeaway

The experiment supports the framework, but it does not yet deliver the final system goal.

What worked:

- one fresh single orchestration was generated and used;
- a 50-instance pool ran end to end on Slurm;
- the first failure trace was converted into a Meta-Orchestrator update;
- the updated orchestration generated 8 apply-checkable candidate patches;
- the official Modal/SWE-bench oracle evaluated those candidates.

What did not work yet:

- no patch was officially resolved;
- the updated policy bought candidates at a high cost;
- `public_literal_repair` improved candidate production but produced false positives;
- patcher/reviewer still do not reliably convert localized evidence into correct semantic edits.

## Next Meta-Update Targets

The next update should be generated by the Meta-Orchestrator from the updated failure bundle, not hand-written.

Recommended constraints to expose to it:

- gate `public_literal_repair` more strictly: source file only, exact old literal present once, new literal supported by public issue text, and surrounding context must match implementation semantics;
- forbid docs/test-only patches unless the issue explicitly asks for docs/tests;
- preserve and evaluate multiple candidates per instance instead of collapsing too early to one final patch;
- add local targeted test selection before Modal;
- separate cheap deterministic actions from expensive model calls in the cost accounting;
- route empty-patch modes to a context-improvement step before another patcher call.

## Main Artifacts

Design:

- `experiments/swebench_orchestration/single_50_fresh/meta_design/orchestration_design.json`

Initial run:

- `swebench/runs/single50_fresh_20260607_110055/executor/predictions.jsonl`
- `swebench/runs/single50_fresh_20260607_110055/executor/traces.jsonl`
- `swebench/evaluations/single50_fresh_20260607_110055_modal_eval/evaluation_manifest.json`

Meta-update:

- `swebench/runs/single50_fresh_20260607_110055/meta_update/meta_update.json`
- `swebench/runs/single50_fresh_20260607_110055/meta_update/orchestration_design_updated.json`
- `swebench/runs/single50_fresh_20260607_110055/meta_update/executor_config_updated.yaml`

Updated run:

- `swebench/runs/single50_updated_20260607_112356/executor/predictions.jsonl`
- `swebench/runs/single50_updated_20260607_112356/executor/traces.jsonl`
- `swebench/evaluations/single50_updated_20260607_112356_modal_eval/evaluation_manifest.json`
