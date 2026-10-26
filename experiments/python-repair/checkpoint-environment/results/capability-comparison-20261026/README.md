# Descriptive capability comparison — 4B, 12B, 27B

This is a **post hoc diagnostic of three separate development banks**, not a
prespecified scaling experiment. All 12 bugs and three response formats remain
included: 36 outputs per model, one draw per bug/format. Task/contract messages
match byte-for-byte; all three engineering gates remain failed.

| Measurement | 4B | 12B | 27B |
| --- | ---: | ---: | ---: |
| Usable source / 36 | 16 | 31 | 34 |
| Mean public-test fraction | 28.7% | 62.7% | 78.1% |
| Mean evaluator-test fraction | 24.1% | 46.2% | 68.8% |
| Full successes / 36 | 1 | 2 | 3 |
| Distinct fully solved bugs / 12 | 1 | 1 | 2 |
| Public-score improvements over original / 36 | 1 | 4 | 14 |
| Public-score regressions below original / 36 | 26 | 11 | 5 |

Higher test fractions accompany larger-model configurations, but this is not
proof of a size effect. The original buggy code already passes **77.5% of public
tests on average**. Thus the 27B's 78.1% public score is only slightly higher on
average, despite more individual improvements than regressions. Test fractions
include already-correct behavior, not just newly fixed failures.

Only Tornado/9 is solved by the 4B and 12B. The 27B also solves youtube-dl/32;
its three successes are one per format, and none reaches the three-bug gate.
Seven of its ten public-test passes fail the separate evaluator suite. A useful
future intervention must repair remaining failures while preserving working
behavior; these counts do not show when continue is better than restart.

## Method and limits

`reproduce.py` validates the three ZIP digests and every archived member before
reading their complete terminal banks. It matches task/format identities,
computes a pass fraction within each cell and then averages cells equally.
Because all bugs have three cells, each bug receives equal weight. It does not
pool individual tests of differently sized suites.

An observed response without a valid file artifact receives score zero by
convention (15 such responses in 4B, none in 12B/27B). This does **not** claim
that unexecuted tests ran and failed. Other syntax/runtime failures retain their
recorded verifier outcomes. This comparison rejects incomplete banks rather
than silently converting missing responses into failures. No record is removed.

These are descriptive values without confidence or significance claims. The
36 outputs are correlated observations on 12 bugs, ten from youtube-dl, and
those bugs were already inspected. Model training exposure differs; 27B uses
FP8 whereas 4B/12B use BF16. Sampling seeds/order and collection pacing differ.
No fitted power law, phase transition, held-out repair benefit or selector gain
is established. No selection threshold or collection protocol is changed.

From repository root:

```bash
.venv/bin/python experiments/python-repair/checkpoint-environment/results/capability-comparison-20261026/reproduce.py \
  --output runs/capability-comparison-reproduced.json
```

The output must equal `analysis.json`; the script sends no network requests.
See the [4B](../contract-deepinfra-20261026/README.md),
[12B](../contract-gemma12b-20261026/README.md) and
[27B](../contract-gemma27b-20261026/README.md) banks for independent sandbox
re-execution, costs and frozen protocols.
