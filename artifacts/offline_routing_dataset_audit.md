# Offline Routing Dataset Audit

Dataset: `artifacts/phase4_teacher_routing_dataset.jsonl`
Total examples: `12`

## Profiles
| key | value |
| --- | ---: |
| `paper_development` | `6` |
| `development` | `3` |
| `memory_development` | `3` |

## Productive Modes
| key | value |
| --- | ---: |
| `layout` | `6` |
| `indexing` | `3` |
| `topk` | `0` |
| `caching` | `1` |
| `summaries` | `0` |
| `micro` | `2` |

## Selected Modes
| key | value |
| --- | ---: |
| `layout` | `5` |
| `indexing` | `2` |
| `topk` | `3` |
| `caching` | `0` |
| `summaries` | `2` |
| `micro` | `0` |

## Class Imbalance
Nonzero class ratio max/min: `6.0`
Missing productive modes: `['topk', 'summaries']`

## Regret
- `count`: `12`
- `mean`: `0.9385370051379591`
- `median`: `0.35313465405577155`
- `min`: `0.0`
- `max`: `4.217488474179428`
- `p10`: `0.0`
- `p90`: `3.2484597429583086`
- `positive_count`: `8`
- `zero_count`: `4`
- `negative_count`: `0`

## Gain By Mode
| mode | count | mean | median | min | max | positive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `layout` | `12` | `0.19277907246350615` | `0.04381220981026207` | `-0.9234994551820046` | `2.9571001775099166` | `8` |
| `indexing` | `12` | `-0.09870471687242628` | `-0.08703880626830951` | `-1.250034641665147` | `0.4419078570964885` | `4` |
| `topk` | `12` | `-0.30990853811163327` | `-0.3361834333708192` | `-0.6197951154957575` | `-0.005546208876104686` | `0` |
| `caching` | `12` | `-0.05535080223654291` | `-0.07013224164902643` | `-0.15959514265662023` | `0.29431722275500694` | `1` |
| `summaries` | `12` | `-2.1357537774621513` | `-2.388070113647286` | `-4.176649382435418` | `0.026001288401479528` | `3` |
| `micro` | `12` | `0.009855020734180367` | `-0.005821925250069637` | `-1.0104889839445255` | `1.7613832069137714` | `6` |

## Declared/Inferred Agreement
Branch count: `72`
Overall agreement: `0.4722222222222222`
| key | value |
| --- | ---: |
| `layout` | `0.4166666666666667` |
| `indexing` | `0.16666666666666666` |
| `topk` | `0.8333333333333334` |
| `caching` | `1.0` |
| `summaries` | `0.25` |
| `micro` | `0.16666666666666666` |

## Duplicates
Exact input duplicate groups: `0`
Exact input duplicate examples: `0`
Solution-hash duplicate groups: `1`
Solution-hash duplicate examples: `4`
Near-duplicate pairs at threshold `0.97`: `6`
