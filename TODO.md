# TODO

## Completed

- [x] Inspect new repository contents.
- [x] Inspect existing `stateful_query_engine` source files.
- [x] Confirm research documents are under `docs/`.
- [x] Create repository layout.
- [x] Add project README and tracking files.
- [x] Copy reusable benchmark components into the new repository.
- [x] Rewrite copied benchmark imports for the new namespace.
- [x] Implement schemas, taxonomy, mode classifier, verifier wrapper, workspaces, adapters, orchestrator, estimators, and dataset builder.
- [x] Run dynamic benchmark/verifier baseline smoke.
- [x] Add and run unit tests.
- [x] Run the two-step six-branch local smoke experiment.
- [x] Compute estimator outputs.
- [x] Generate routing dataset JSONL.
- [x] Generate a simple endpoint table.
- [x] Write `EXPERIMENT_REPORT.md`.
- [x] Initialize git and commit the smoke-pass framework.
- [x] Add C(a) run validator.
- [x] Add explicit anti-leakage pytest coverage.
- [x] Add parent-loss audit logging.
- [x] Run 3-profile x 3-repeat x 5-step deterministic Phase 2 expansion.
- [x] Validate every Phase 2 run.
- [x] Generate Phase 2 estimator CSV, routing JSONL, and summary JSON.
- [x] Add Claude Haiku backend with strict structured output parsing.
- [x] Add prompt templates for distribution, edit generation, JSON repair, and code repair.
- [x] Add fixture-based Claude parser and prompt rendering tests.
- [x] Run Haiku smoke: 1 profile, 2 steps, 12 branches.
- [x] Run Haiku dev: 3 profiles, 1 run each, 3 steps each.
- [x] Generate Phase 3 Haiku estimator, routing, summary, and failure-mode artifacts.
- [x] Convert Claude Haiku candidate outputs from full-file replacement to patch-based `unified_diff` edits.
- [x] Add strict unified-diff application and tests for patch parsing/application failures.
- [x] Run corrected Phase 3.5 Haiku patch smoke and 3-profile dev validation.
- [x] Compare Phase 3 replacement-file and Phase 3.5 patch-based protocols.
- [x] Freeze production teacher-data protocol as replacement-file C(a).

## Remaining

- [ ] Run Opus teacher pilot with the frozen replacement-file protocol.
- [ ] Generate first validated Opus teacher routing dataset.
- [ ] Implement routing-only student training and offline evaluation.
- [ ] Run online routing-student comparison if integration remains straightforward.
- [ ] Replace adapter scaffolds with real Claude Code and OpenAI-compatible model calls when credentials/endpoints are available.
- [ ] Add pre-verifier dynamic source smoke tests for generated candidate constructors and common operations.
- [ ] Improve prompts for `indexing` and `micro` declared-mode adherence.
- [ ] Add controlled shared-checkpoint phi experiment implementation.
- [ ] Add full C(b) pre/post feedback distribution diagnostic.
- [ ] Add training implementation for `train_routing_lora.py`.
- [ ] Run larger multi-profile and holdout experiments after protocol validation is reviewed.
