# Haiku vs Qwen R0-R4 Failure Analysis

## Main Findings

- Haiku branch correctness is `182/300`; selected-branch correctness is low because selected modes include many non-finite/incorrect candidates.
- Qwen branch correctness is `300/300`, but it selected `layout` `47/50` times while verified-best modes were distributed across all six modes.
- New preflight replay on Haiku historical branches catches `99` of `118` invalid branches (`0.839`) with `0` false rejects among `182` correct branches.

## Haiku Preflight Replay

| reason | count |
| --- | ---: |
| `operation_divergence` | `43` |
| `constructor_failed` | `29` |
| `candidate_import_failed` | `21` |
| `operation_exception` | `6` |

## Selected vs Verified Best Counts

| backend | selected layout | selected non-layout | best layout | best non-layout |
| --- | ---: | ---: | ---: | ---: |
| `haiku_batch` | `23` | `27` | `14` | `27` |
| `qwen_direct` | `47` | `3` | `13` | `37` |

## Branch Correctness By Mode

| backend | layout | indexing | topk | caching | summaries | micro |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `haiku_batch` | `31/50` | `29/50` | `28/50` | `31/50` | `29/50` | `34/50` |
| `qwen_direct` | `50/50` | `50/50` | `50/50` | `50/50` | `50/50` | `50/50` |

## Artifacts

- `artifacts/haiku_vs_qwen_r0_r4_failure_analysis.json`
