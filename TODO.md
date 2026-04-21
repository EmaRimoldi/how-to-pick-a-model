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

## Remaining

- [ ] Replace adapter scaffolds with real Claude Code and OpenAI-compatible model calls when credentials/endpoints are available.
- [ ] Add controlled shared-checkpoint phi experiment implementation.
- [ ] Add full C(b) pre/post feedback distribution diagnostic.
- [ ] Add training implementation for `train_routing_lora.py`.
- [ ] Run multi-profile and holdout experiments after smoke results are reviewed.
