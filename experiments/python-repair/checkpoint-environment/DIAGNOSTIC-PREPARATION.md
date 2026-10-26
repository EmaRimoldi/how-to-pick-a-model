# Public execution diagnostics: offline preparation

Status: implemented engineering prototype; **no live collection or model claim**.
Research motivation and stop rules are in the [goal amendment](GOAL-AMENDMENT-20261026.md).
The subsequent [prospective collection protocol](INFORMATION-PROTOCOL.md) now
specifies exact draws, analysis, accounting and launch requirements. This earlier
offline preparation document remains the adapter's engineering contract.

The adapter accepts only public task data and a candidate artifact. It runs the
existing public suite, chooses the first failed case in its declared order,
re-executes it without instrumentation and with a bounded execution tracer.
All three observed results must match before the trace is made available.
No public failure means no probe, regardless of evaluator outcomes.

The worker receives the candidate, entrypoint and public input only. Expected
answers remain in the parent. It traces only declared candidate files, never
standard-library/worker frames, reference code or evaluator cases. It records
line, return and exception events, with line locals captured **before** execution.
At most 32 recent events / 12,000 event bytes are retained from the first 512
captured events. Up to eight locals and bounded exact built-in values are shown;
custom objects are omitted without calling their `repr`. Truncation is explicit.
An instrumented run can time out, disagree or lose tracing; such records remain
unavailable rather than becoming invented feedback. This consistency check does
not certify arbitrary adversarial code, all future inputs or trace completeness.

Three inert request projections preserve the same code, specification, public
tests, feedback and JSON output contract:

| Arm | Additional information |
| --- | --- |
| `raw` | None; all existing public case results remain visible |
| `focused` | Repeats the first failing public input, expected result and observation; no new facts |
| `focused_trace` | The same focus plus the bounded trace, or an explicit unavailable marker |

These are prompt controls, not equal-token prompts. A later experiment must
count their differing input tokens. The engineering demo prepares all three
offline; a real direct-retry baseline must not acquire traces or pay for them.
Shared public verification is charged once per checkpoint. Diagnostic acquisition
adds two local executions and measured wall time; no dollar conversion for local
compute is assumed.

```bash
.venv/bin/python scripts/prepare_repair_diagnostics.py \
  --public-task experiments/python-repair/checkpoint-environment/fixtures/record-normalization/task.json \
  --output runs/public-trace-demo
```

An optional `--artifact` supplies a filename-to-source JSON. The command refuses
existing output directories and never imports provider transport. The output
contains source hashes, exact public inputs, observation, trace, costs in local
executions/time, and the three disabled requests.

## Next prospective development experiment — design requirements

Use one failed candidate per bug selected by a fixed public-only rule, keeping
all noneligible bugs in the accounting. Prefer the saved 27B `json_current`
candidate as a declared engineering convention; **that contract did not pass
the previous calibration gate**. Public passes, invalid code, instrumentation
failures and ambiguous tasks cannot be silently removed to improve results.

Before dispatch, freeze eligibility, task versions, provider route/precision,
sampling, draw count/order, one-call limit per arm, complete request bodies,
analysis and budget. The primary diagnostic contrast is `focused_trace` minus
`focused`; `focused` minus `raw` checks presentation. Use repeated samples grouped
by bug, retain all costs/missing requests, and analyze only after termination.
An omnibus increase in partial tests is insufficient: require repeatable complete
repairs before designing a larger acquisition-policy evaluation. These twelve
bugs are development data; neither they nor viewed evaluator cases are a new
holdout. Numerical gates and sample sizes for a later untouched evaluation must
be fixed before seeing its outcomes, not reverse-engineered from this pilot.

The existing twelve-task contracts are not edited by this prototype. The
timestamp ambiguity recorded in the audit must be resolved in a separately
versioned development specification before it can support a semantic claim.
No repair request is admitted by this preparation document.
