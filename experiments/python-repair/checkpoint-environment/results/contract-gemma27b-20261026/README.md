# Gemma 3 27B capability control — complete, gate failed

All 36 initial repairs finished under the [frozen protocol](../../CONTRACT-27B-PROTOCOL.md).
No missing or uncertain new request. The unchanged gate fails: each format solves
one of twelve bugs, below the required three distinct solved bugs per format.
No format is selected and no repair selector is trained.

| Format | Usable source / 12 | Full public + evaluator successes / 12 | Public-only passes |
| --- | ---: | ---: | ---: |
| Current JSON | 12 | 1 | 4 |
| Example JSON | 12 | 1 | 3 |
| Python text | 10 | 1 | 3 |

Both JSON successes concern youtube-dl/32; the text success concerns Tornado/9.
Thus three successful outputs cover **two distinct bugs**, not three. Seven of
ten outputs passing all public tests still fail evaluator tests. Both suites
remain reported; public success alone would overstate correctness.

A post hoc structural diagnostic finds only **2/34 syntax-valid outputs
AST-unchanged**. Structural changes are not assumed beneficial. The separately
labeled [three-bank comparison](../capability-comparison-20261026/README.md)
retains partial test progress and regressions without changing this gate.

## Accounting and verification

Known study charges: **$0.00450984 / $0.13**. Carry $0.01760731 exactly once:
**$0.02211715 / $0.60 cumulative**, including the five unresolved historical
reserves. No old reserves were released or requests repeated. Local verification
resources are separate from API charges; this is not an equal-total-cost policy
comparison.

Freeze `5c3a4e72e16ea01d01e7ccb9da1373063d35ff8842d7f200039d56a06a59f74b`
binds source `4484ada0e6b59b3979be516eb23e4ecec1f81c0a`. The source passed
[CI](https://github.com/EmaRimoldi/how-to-pick-a-model/actions/runs/40316863183)
and 233 offline tests (five skipped) before collection. The evidence archive
contains exact requests, raw/normalized receipts, accounting, all artifacts and
inert frozen source snapshots. Its SHA-256 is
`f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913`.

Independent extraction reproduced all JSON and Markdown fields exactly.
**72 evaluation records / 64 unique artifact-suite inputs** were re-executed
in the OS sandbox, with **zero discrepancies and zero API calls**.

From repository root, with the project environment installed:

```bash
.venv/bin/python scripts/verify_repair_contract_evidence.py \
  --input experiments/python-repair/checkpoint-environment/results/contract-gemma27b-20261026 \
  --output runs/27b-independent-reverification.json
```

For the optional post hoc AST diagnostic, extract `evidence.zip` into a fresh
folder and use the existing generic diagnostic entry point:

```bash
.venv/bin/python experiments/python-repair/checkpoint-environment/results/contract-gemma12b-20261026/diagnose.py \
  --input /path/to/extracted/collection --output runs/27b-ast-check.json
```

Its output must equal `artifact-diagnostic.json`. Use fresh output paths.

## Interpretation

This is one draw per contract on twelve inspected, function-level BugsInPy
adaptations, ten from one project. It is neither held-out evaluation nor
continue/restart recovery. DeepInfra 27B uses FP8; the earlier 4B/12B routes
used BF16. Seeds, order, training exposure and collection time also differ.
There is no causal size estimate, emergence threshold or scaling law here.
The complete-bank engineering gate is unchanged. Further diagnosis of semantic
errors and verifier false positives is needed before another frozen recovery
study; these results do not authorize selector training.
