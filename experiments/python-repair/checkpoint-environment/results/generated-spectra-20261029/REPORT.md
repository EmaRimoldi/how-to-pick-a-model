# Public coverage on model-generated failed checkpoints

Offline development audit; no model calls or efficacy inference. Twelve source candidates retained; four pass public tests and do not trigger acquisition.

| Generated checkpoint | Pass/fail cases | Failing-executed lines | Positive score groups | Top-score tie |
| --- | ---: | ---: | ---: | ---: |
| youtube-dl-003 | 5/1 | 11 | 5 | 1 |
| youtube-dl-013 | 5/1 | 8 | 4 | 2 |
| youtube-dl-020 | 5/1 | 7 | 1 | 7 |
| youtube-dl-031 | 5/1 | 11 | 4 | 1 |
| youtube-dl-033 | 5/1 | 15 | 4 | 4 |
| youtube-dl-042 | 4/2 | 7 | 3 | 2 |
| youtube-dl-043 | 5/1 | 4 | 2 | 1 |
| httpie-005 | 4/2 | 18 | 2 | 9 |

8/8 complete spectra; 7/8 distinguish scores among lines executed by failing cases.
48 public cases; 96 additional executions plus one sandbox preflight; 7.392 seconds in the saved acquisition.

- Previously exposed Gemma 3 27B json_current failed candidates; eight public failures out of twelve candidates, not unseen policy evaluation.
- Ranks correlate line execution with existing public labels; they do not locate a known fault.
- No reference patch or private evaluator used; no repair, selection or benefit measured.
- Only single-threaded entrypoint calls after module import are instrumented.
- Python line events do not show sub-line data dependencies, C internals or absent code.
- No truncated coverage or partial suite is scored; all failures remain in the denominator.
- Elapsed time is machine-specific and is not a model cost or equal-total-budget experiment.
- Retain whole tie groups; a small top tie group is not a criterion to enable model collection.
- Different bugs and source states from the original-bug audit; no causal comparison between the two audits.
