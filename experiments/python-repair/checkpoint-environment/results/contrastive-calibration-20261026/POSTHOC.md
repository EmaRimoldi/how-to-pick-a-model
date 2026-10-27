# Post hoc failure audit: local correction versus complete repair

This audit was run only after the 72-request bank ended and its fixed analysis
and 144 evaluation records were independently reproduced. It retains all twelve
source candidates and all 72 responses. It does not change the primary 6/9/9
result, development screen or any historical experiment. No model calls or
candidate executions are made by this audit; the archived evaluations provide
the outcomes.

| Observable | Code + feedback | + Failing trace | + Failing/passing traces |
| --- | ---: | ---: | ---: |
| Outputs correcting some original public failure | 12 | 18 | 16 |
| Outputs correcting the failure selected for tracing | 9 | 15 | 14 |
| Complete public-plus-evaluator repairs | 6 | 9 | 9 |
| Outputs breaking any initially passing public case | 7 | 3 | 3 |
| Public passes rejected by evaluator | 2 | 3 | 2 |
| Syntactically invalid outputs | 2 | 1 | 1 |

These overlapping counts are descriptive. Any-case regression differs from the
net-score regression in the fixed report: a repair can fix one test and break
another without lowering its overall score. Across all arms, 46 outputs correct
at least one original failure but only 24 completely repair. Four outputs cannot
load, two exactly copy their source and three change only formatting/comments;
63 change other syntax. Literal copying and response parsing are therefore not
the dominant observed failure categories in this bank.

## Cases that constrain the next intervention

- **youtube-dl-042:** five trace-bearing responses fix the selected `existing`
  case but leave the other initially failing `raw` case unresolved. All three
  paired-trace draws are among these. Their trace pair describes preserving one
  entity; it does not demonstrate correct handling of multiple ampersands.
  Both original failure observations were already in the common prompt, so this
  cannot be described as a missing public expected answer. The examples suggest
  an unresolved repair requirement, not a proved causal attention mechanism.
- **httpie-005:** no arm repairs the selected `long-escape` failure. Examples
  change the separator logic but still split an escaped overlapping separator.
  More trace context has not supplied a successful implementation here. All
  nine failures remain; this task is not removed to improve the aggregate.
- **youtube-dl-013 and youtube-dl-031:** some outputs fix the selected case and
  pass public checks while missing stated preservation behavior in evaluation
  (scheme-relative URLs; whitespace or zero durations). These evaluator findings
  are audit-only. They cannot become deployable hints or new public tests under
  the unchanged contract.
- **youtube-dl-020:** the fixed input-similarity rule pairs a successful match
  expectation with a passing no-match input. A passing execution need not be a
  useful semantic contrast. Changing that pairing rule would be a new intervention,
  not a reinterpretation of this completed study.

All eight failing traces are available; seven drop no events, none reaches the
capture ceiling, and six contain explicit value-omission markers. The audit also
retains metrics for each passing trace. Neither truncation nor coverage alone
explains the repair outcomes. No counterfactual representation was tested here.

## Consequence for research

The verified problem is incomplete implementation and preservation, with partial
progress often exceeding complete-task success. This supports revisiting **which
failure evidence is acquired and at what checkpoint**, rather than training a
selector on the current sparse action labels. It does not prove that a proposed
replacement diagnostic will help or identify a unique root cause.

Before another paid study, compare concrete public-only candidates: evidence for
all currently failing cases, a more relevant passing contrast, or test/trace
acquisition on the updated artifact after a partial repair. Keep the strongest
fixed alternative that has the same permitted information and pays its real
cost. The [information-access review](../../INFORMATION-ACCESS-REVIEW.md) explains
why artificially hiding cheap available tests or injecting evaluator answers
would not establish value. Any new acquisition needs a separate contract and
prospective test; no selector training is warranted by this audit.

## Reproduction

[posthoc-audit.json](posthoc-audit.json) binds every response to archive
`3205581a96e28f215cae5b23122cda831888c231ccd1a2b04b1eb69af61ac1a6`.
The implementation checks every archive member and source/response identity,
uses inert AST parsing only, and retains corrected, regressed, still-failed and
preserved public case IDs for every response. Private case IDs are explicitly
audit-only. Tests preserve exact historical audit output and check the new
three-arm bank plus untriggered metadata handling.

```bash
uv run python scripts/audit_repair_trace_information.py \
  --input experiments/python-repair/checkpoint-environment/results/contrastive-calibration-20261026 \
  --output runs/contrastive-posthoc-audit.json
```

Use a fresh output path. The post hoc audit is not a new efficacy comparison,
causal explanation, selector validation or evidence of scaling.
