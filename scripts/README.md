# Repository Scripts

`prepare_progress_history.py` prints the next experiment's offline plan by default.
With a fresh `--output`, it writes synthetic development fixtures and exact
verifier checks. No live mode or model responses; see the
[progress-history design](../experiments/finite-domain/progress-history/README.md).

`verify_feedback_evidence.py` reproduces the complete published BigCodeBench
bank without credentials, provider calls or candidate execution: file checksums,
frozen sources, receipt/prompt projection, fixed statistics, verifier-repeat
record and preservation of the single requested interim prefix.
`analyze_feedback_routing.py` is the frozen scientific analyzer;
`report_feedback_routing.py` publishes an ended bank with inert source snapshots,
diagnostic accounting and PNG/SVG figures. The completed collector must not be
restarted; see the [study guide](../experiments/bigcodebench/feedback-only-routing/README.md).

`run_recovery_transfer.py` defaults to planning the prospectively frozen MBPP+
replication. Live calls need explicit live, stdin-key and remaining-budget
arguments; read the [protocol](../experiments/mbpp-plus/context-value-transfer/PROTOCOL.md).
`analyze_recovery_transfer.py` audits recorded receipts, frozen source-trained
weights and matched cells, then reproduces the specified comparisons without
provider access or candidate execution.

## Navigation and validation

- `build_repo_inventory.py`: retained-tree inventory, with logical LFS sizes.
- `build_knowledge_index.py`: code, theory, experiment, and active-reference map.
- `build_experiment_manifest.py`: assets and reproducibility status by bundle.
- `build_command_manifest.py`: command prerequisites and safety classes.
- `validate_agent_readiness.py`: generated-map freshness, core evidence,
  references, duplicate policy, and local-path/link checks.
- `agent_index_config.py`: shared configuration, not a command entrypoint.
- `check_paper_build.py`: out-of-tree build of both retained manuscripts.

```bash
make indexes
make check
make paper-build
```

## Existing baseline helpers

`analyze_runs.py`, `compare_experiments.py`, `benchmark_parallel_capacity.py`,
`run_single_long_experiment.py`, `run_parallel_experiment.py`,
and `run_merge_phase.py` support the existing CLI
baseline runtime. Launch helpers may invoke live models or compute; use the
command safety manifest and explicit run authorization.

`agent-workflow merge` is the canonical merge command; `run_merge_phase.py` is
its compatibility entrypoint. Both use `agent_workflow.modes.merge` and the
shared merge orchestrator.

`bootstrap_engaging.sh` is a historical HumanEval+ cluster environment helper.
Current portable setup is documented in `docs/reproducibility.md`.

AutoResearch reproduction and campaign commands live under `autoresearch/scripts/`.

## Recovery collection and archived pilot

`run_continuation_pilot.py` writes a plan by default. Paid requests require
`--live --budget-usd` and credentials; see the
[archived pilot provenance](../experiments/humaneval-plus/context-value/provenance/continuation-pilot/README.md).
The legacy runner remains for shared-runtime compatibility, not as a maintained study.

`run_context_value.py` plans by default and requires the same explicit live/budget
flags for the [context-value diagnostic](../experiments/humaneval-plus/context-value/README.md).
`analyze_context_value.py --input RUN --output NEW_DIRECTORY` audits saved
receipts, parent identities, observable prompts and forecast order, then writes
paired task-cluster analysis and a figure. It makes no provider calls.

`run_recovery_validation.py` plans the task-held-out validation by default.
Live collection requires its explicit remaining campaign budget; it freezes
development-trained policies before evaluation calls. The
[frozen protocol](../experiments/humaneval-plus/context-value/VALIDATION.md)
defines the new public-base feedback regime and reserved tasks.

`analyze_recovery_validation.py --input RUN --output NEW_DIRECTORY` audits recorded
data and replays the fixed two-draw policy bank, including all static controls.
It makes no provider call and executes no candidate. The
[curated transfer report](../experiments/humaneval-plus/context-value/results/validation-20261022/report.md)
and [blog draft](../docs/blog/when-to-keep-failed-code.md) explain the results.
