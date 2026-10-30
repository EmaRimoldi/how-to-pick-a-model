# Public coverage feasibility audit

Offline development audit; no model calls or efficacy inference.

| Original bug | Pass/fail cases | Failing-executed lines | Positive score groups | Top-score tie |
| --- | ---: | ---: | ---: | ---: |
| scrapy-002 | 4/2 | 7 | 3 | 2 |
| scrapy-036 | 3/3 | 20 | 7 | 1 |
| luigi-010 | 4/2 | 9 | 2 | 1 |
| tornado-005 | 4/2 | 12 | 3 | 3 |
| thefuck-022 | 4/2 | 25 | 6 | 2 |
| thefuck-029 | 2/4 | 7 | 1 | 7 |
| scrapy-026 | 3/3 | 58 | 4 | 9 |
| scrapy-040 | 3/3 | 49 | 6 | 3 |

8/8 complete spectra; 7/8 distinguish scores among lines executed by failing cases.
48 public cases; 96 additional executions plus one sandbox preflight; 4.708 seconds in the saved acquisition.

- Original buggy artifacts, not model-generated failed checkpoints; all development-exposed.
- Ranks correlate line execution with existing public labels; they do not locate a known fault.
- No reference patch or private evaluator used; no repair, selection or benefit measured.
- Only single-threaded entrypoint calls after module import are instrumented.
- Python line events do not show sub-line data dependencies, C internals or absent code.
- No truncated coverage or partial suite is scored; all failures remain in the denominator.
- Elapsed time is machine-specific and is not a model cost or equal-total-budget experiment.
- Retain whole tie groups; a small top tie group is not a criterion to enable model collection.
