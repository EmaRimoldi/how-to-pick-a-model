# Diagnostic Run Cleanup - 2026-04-22

Removed raw run directories that were failed probes, superseded diagnostics, or incomplete retries excluded from primary aggregates.

Kept validated primary runs used in current summaries, including:

- Haiku/Qwen R0-R4 validated aggregate runs.
- Strict single-prompt Haiku and Qwen Coder successful smokes.
- GPT/Codex CLI successful one-step smokes.
- Phase 2 protocol-validation runs.
- Phase 4/5 validated teacher/student runs.

Removed directories:

| path | reason |
|---|---|
| `runs/hard_profile/single_prompt/model_matrix/hard_gpt54mini_codex_cli_single_prompt_smoke_1step_r0` | failed first Codex CLI schema attempt; superseded by validated `r1` |
| `runs/hard_profile/single_prompt/model_matrix/hard_sonnet_single_prompt_smoke_1step_r0` | Sonnet full-step timeout; no `evaluations.jsonl` |
| `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_coder_single_prompt_smoke_1step_r0` | malformed first Qwen Coder batch output; superseded by validated prompt-fix run |
| `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_local_cached_single_prompt_smoke_1step_r0` | cached local Qwen negative diagnostic; no branch evaluations |
| `runs/hard_profile/single_prompt/qwen_batch_structured/hard_qwen_local_cached_single_prompt_smoke_1step_r0_retry1` | cached local Qwen retry diagnostic; no branch evaluations |
| `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_claude_opus_teacher_memory_development` | failed/incomplete pilot attempt; superseded by validated retry |
| `runs/phase4_teacher_opus_pilot/opus_teacher_pilot_retry_claude_opus_teacher_memory_development` | failed/incomplete pilot retry; superseded by validated retry2 |
| `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r3` | incomplete Haiku trial excluded from R0-R4 aggregate |
| `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r3_retry1` | incomplete Haiku retry excluded from R0-R4 aggregate |
| `runs/hard_profile/haiku_vs_qwen/haiku_batch/hard_haiku_batch_10step_r4` | incomplete Haiku trial excluded from R0-R4 aggregate |
| `runs/phase35_patch/haiku_smoke/haiku_patch_smoke` | superseded Phase 3.5 patch smoke; corrected `haiku_patch_smoke_v2` retained |
| `runs/phase3_real_backend/haiku_smoke/haiku_structured_smoke_speed` | speed diagnostic raw run; summary artifacts retained |
| `runs/phase3_real_backend/haiku_structured_batch_smoke/haiku_structured_batch_speed` | speed diagnostic raw run; summary artifacts retained |
