# AutoResearch model-menu smoke test

Config: `configs/autoresearch_cifar10_model_routing_smoke.yaml`

Date: 2026-05-01

## Result

All four declared paper-facing models responded successfully to a minimal one-shot CLI smoke prompt.

| Model key | Backend | Model id | Status |
| --- | --- | --- | --- |
| `gpt_5_4_mini_batch_strict` | codex_cli | `gpt-5.4-mini` | ✅ |
| `gpt_5_3_codex_batch_strict` | codex_cli | `gpt-5.3-codex` | ✅ |
| `gpt_5_3_codex_spark_batch_strict` | codex_cli | `gpt-5.3-codex-spark` | ✅ |
| `claude_sonnet_batch_strict` | claude_haiku (CLI transport) | `sonnet` | ✅ |

Raw machine-readable output: `artifacts/autoresearch_cifar10/model_menu_smoke.json`
