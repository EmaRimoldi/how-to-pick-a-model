# Routing Failure Analysis

Selected offline model: `tfidf_word_multinomial_nb`.

## Main Bottlenecks

- Dataset size is only `12` examples.
- Productive-mode class counts are `{'caching': 1, 'indexing': 3, 'layout': 6, 'micro': 2, 'summaries': 0, 'topk': 0}`; `topk` and `summaries` have zero positive labels.
- Max/min nonzero class imbalance is `6.0`.
- Near-duplicate pair count is `6`, mostly initial checkpoints.
- Declared/inferred branch agreement is `0.4722222222222222` across logged branches.

## Student Failures

- Leave-one-out selected model accuracy: `0.5`.
- Failure count: `6` of `12`.

| profile | count | accuracy | mean regret |
| --- | ---: | ---: | ---: |
| `development` | `3` | `0.0` | `1.0216142494473144` |
| `memory_development` | `3` | `1.0` | `0.0` |
| `paper_development` | `6` | `0.5` | `0.15874691293923254` |

## Teacher Routing Suboptimality

- Teacher/original top-1 regret is positive on `8` of `12` examples.
- Mean original top-1 regret: `0.9385370051379591`.
- Max original top-1 regret: `4.217488474179428`.

## Label Ambiguity

- Multiple modes within 0.05 verified gain of best: `2` examples.
- Multiple positive-gain modes: `7` examples.
- Mean productive-distribution entropy: `0.7286313124823991`.

## Interpretation

The current routing data is enough to test plumbing and replay metrics, but it is not enough to support a reliable learned router. The easiest baseline, `always_layout`, is strong because `layout` dominates the productive labels. More balanced teacher data is the immediate bottleneck before within-mode or feedback-use training.
