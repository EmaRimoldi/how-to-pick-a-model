# Stateful-source feasibility: the tail trace omits the failing method

This is an offline engineering probe of one already-exposed development bug,
Scrapy/26. It is **not** another model cohort, a resumed study, a held-out result
or evidence that a new diagnostic improves repair. No API calls were made.

Six pinned upstream role files are retained with URLs and hashes in
`sources.json`, including the license. Complete original definitions of
`SettingsAttribute`, `BaseSettings`, `_DictProxy`, `get_settings_priority` and
the priority constant are extracted unchanged. Python 3 import compatibility,
the two used `six` operations and a JSON wrapper are explicit in `probe.py`.
Crawler setup, module loading and other settings APIs are outside this probe.

Four manually specified input/expected-output examples were saved before either
variant executed. The buggy source passes **2/4**, while its original fix passes
**4/4**. Every ordinary/traced observation agrees. The two failing examples
exercise nested settings priorities and exclusion of default entries when an
explicit base is supplied, following the upstream contract.

| Buggy source example | Events observed | Events dropped | Retained events in `_getcomposite` |
| --- | ---: | ---: | ---: |
| Default entries excluded by explicit base | 408 | 376 | 0 |
| Explicit empty base | 279 | 247 | 0 |
| No base supplied (passing control) | 185 | 153 | 0 |
| Preserve higher priority (passing control) | 267 | 235 | 2 |

The worker retains the last 32 events within its byte limit. Here, later
formatting/access calls displace the method that implements composition. Its
512-event capture limit was not reached. This demonstrates a concrete retention
failure for these inputs; it does **not** establish why previous model studies
failed their screens. The known changed method is used only to audit retained
coverage after execution, never to select solver-facing trace events.

A future diagnostic should test coverage across call boundaries or program
regions while preserving actual observed values, explicit omissions and a bounded
message. Selection cannot use the reference fix or private evaluator, and all
collection/selection costs must be charged. Wider retention or larger budgets
alone are not evidence of model benefit. The current worker and all frozen
historical studies remain unchanged.

## Relevant precedents and limits

[LDB](https://aclanthology.org/2024.findings-acl.49/) uses intermediate states at
basic-block boundaries for debugging. It motivates checking which execution
regions survive in a bounded diagnostic; our proposed engineering revision is
not yet an LDB implementation or replication.

[Haque et al.](https://arxiv.org/html/2505.04441v1), sections 4.1–4.2, study trace
compression and routing by model confidence or trace length. They do not find
strong evidence that length routing is generally beneficial. Their routing
observes an already acquired trace; our eventual acquisition selector must
account for the cost and timing of obtaining that information. This distinction
is a research constraint, not by itself a novelty claim. Their findings do not
validate a particular truncation rule or prove our proposed revision will help.

## Reproduce

```bash
uv run python experiments/python-repair/checkpoint-environment/results/stateful-trace-feasibility-20261027/probe.py \
  --output runs/stateful-trace-feasibility-replay
```

Check all pinned source hashes first. Compare outcomes, event counts, functions,
trace contents and source hashes in the saved/replayed JSON; ignore only measured
verification durations. `runtime-hashes.json` identifies the measured verifier
and tracing sources. Use the documented macOS sandbox; no unrestricted execution
or model requests occur. Four engineering examples do not qualify a future
public/evaluator task bank or establish model difficulty.
