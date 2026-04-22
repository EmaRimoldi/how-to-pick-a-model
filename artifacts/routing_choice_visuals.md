# Routing Choice Correctness

Primary correctness criterion: selected top-probability mode is one of the verified best-gain modes for that checkpoint.

| dataset | steps | correct | incorrect | accuracy | mean regret |
| --- | ---: | ---: | ---: | ---: | ---: |
| `haiku_vs_qwen_r0_r4` | `100` | `34` | `66` | `0.34` | `0.19405137723775723` |
| `phase4_opus_teacher` | `12` | `4` | `8` | `0.3333333333333333` | `0.9385370051379591` |

## Phase 4 Opus Teacher

- Correct choices: `4`
- Incorrect choices: `8`
- Accuracy: `0.3333333333333333`
- Mean routing regret: `0.9385370051379591`
- Zero-regret steps: `4`
- Positive-regret steps: `8`

### By Profile

| profile | steps | correct | incorrect | accuracy |
| --- | ---: | ---: | ---: | ---: |
| `development` | `3` | `0` | `3` | `0.0` |
| `memory_development` | `3` | `2` | `1` | `0.6666666666666666` |
| `paper_development` | `6` | `2` | `4` | `0.3333333333333333` |

### Selected Mode Counts
| mode | count |
| --- | ---: |
| `layout` | `5` |
| `indexing` | `2` |
| `topk` | `3` |
| `caching` | `0` |
| `summaries` | `2` |
| `micro` | `0` |

### Verified Best Mode Counts
| mode | count |
| --- | ---: |
| `layout` | `5` |
| `indexing` | `3` |
| `topk` | `0` |
| `caching` | `2` |
| `summaries` | `0` |
| `micro` | `2` |

### Plots
- accuracy_by_dataset: `artifacts/plots/routing_accuracy_by_dataset.png`
- teacher_correct_vs_wrong: `artifacts/plots/phase4_teacher_correct_vs_wrong.png`
- teacher_selected_vs_best_counts: `artifacts/plots/phase4_teacher_selected_vs_best_counts.png`
- teacher_confusion: `artifacts/plots/phase4_teacher_confusion_selected_vs_best.png`
- teacher_regret_by_step: `artifacts/plots/phase4_teacher_regret_by_step.png`
