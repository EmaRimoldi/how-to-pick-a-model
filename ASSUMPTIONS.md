# Assumptions

- `Document_2_Implementation_Guide.md` is the operational source of truth because local PDF text extraction is unavailable.
- The original `/Users/emanuelerimoldi/Documents/GitHub/stateful_query_engine` repository is read-only for this work session. Reused source is copied into the new repository.
- The new project directory is not a Git repository at the start of work, so the requested phase commits are skipped unless a `.git/` directory appears later.
- External model backends may be unavailable. The first complete experiment uses `local_stub`, a deterministic mock backend that satisfies the same six-mode protocol.
- Incorrect or invalid branches remain part of the branch tensor and estimator calculations. They receive the configured incorrect gain penalty for routing diagnostics.
- In the default C(a) `top1_only` regime, the selected top-probability branch is promoted even if it is incorrect, matching the protocol's online visibility rule.
- The first implementation prioritizes clean routing supervision data and smoke validation; LoRA/QLoRA training entrypoints are scaffolded but do not train unless explicitly run later.
- Routing gain targets are computed over the requested/declared branch mode so every step has exactly one candidate per mode. Inferred modes are also logged and used by mode-conditioned diagnostic summaries.
- The smoke run uses the full `paper_development` profile rather than a reduced toy profile for the protocol-level experiment.
- Phase 2 deterministic expansion uses reduced `instance_overrides` inside the three named dev profiles. This keeps validation inexpensive while still exercising three profile IDs and all protocol machinery.
- In C(a), previous `mode_probs` remain visible in history because they are part of the model's own prior decision state. Offline branch feedback for non-selected modes is the leakage-sensitive object and is excluded from next-step visible branch history.
- Phase 2 run directories remain under `runs/phase2_dev/`; repository `.gitignore` excludes `runs/*`, so committed Phase 2 outputs are the compact artifacts under `artifacts/` plus configs/tests/code.
