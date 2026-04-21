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
- Phase 3 used Claude CLI transport because `ANTHROPIC_API_KEY` was not present. The backend also includes a direct Anthropic Messages API transport for environments with an API key.
- The configured `claude_haiku` model id is `haiku`, which the local Claude CLI mapped to a current Haiku model during live runs.
- Phase 3 uses reduced benchmark `instance_overrides` for the named profiles, matching Phase 2's protocol-validation style and keeping verifier runtime bounded.
- Claude CLI token counts include cache creation/read tokens from Claude Code's runtime context. They are useful for cost tracking but should not be interpreted as minimal prompt-token counts for a direct Messages API implementation.
- For future Claude runs, candidate generation is patch-based: the model must emit a `unified_diff` edit for the branch-local parent. The verifier still receives a complete `proposed_solution.py`, but that file is materialized by applying the patch rather than by asking the model to regenerate the full source.
- Deterministic local/mock backends may continue to write complete candidate files directly because they are protocol-test utilities, not cost-sensitive real-model editing backends.
