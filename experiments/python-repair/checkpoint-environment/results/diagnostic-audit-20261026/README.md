# Post hoc failure audit and public diagnostic engineering check

This audits the closed 27B bank and tests a new offline diagnostic adapter. It
does not change historical scores, prove a repair intervention works, or train
a selector. The [goal amendment](../../GOAL-AMENDMENT-20261026.md) records the
user-requested research direction and its literature basis.

## Seven false-positive outputs, three distinct bugs

All archive and member hashes are checked against the published 27B manifest.
The exact specifications, failing evaluator inputs and observed outputs are
retained in [analysis.json](analysis.json). The classification below is a
post hoc interpretation by the researcher, not an automatically verified label.

| Bug | Outputs passing public but failing evaluator tests | Diagnosis |
| --- | ---: | --- |
| youtube-dl/11 | 3 | The specification says preserve numeric inputs. An integer works, but float `1.25` raises `TypeError`: an explicit requirement is missed by the public suite. |
| Tornado/9 | 2 | With `args=None`, the specification requires the original URL exactly. Normalization removes the `?` from `http://example.org/p?#x`: another explicit requirement violation. |
| youtube-dl/27 | 2 | `00:00:00:5` returns `0.005`, but evaluation expects `0.5`. The instruction calls the suffix a fractional part and also describes a three-digit example as milliseconds. Those descriptions leave a plausible competing interpretation for short suffixes. Treat this as a specification ambiguity, not clean evidence of model incapacity. |

All twelve task instructions and finite case lists were read in this audit.
The timestamp wording is the specific ambiguity identified here; this is not an
independent specification certification. The original seven failures and all
three-format/three-model denominators remain unchanged. No post hoc rescoring,
benchmark repair, selective task removal or improved model claim is made.
Any future clarification must create a separately versioned development task;
the exposed evaluator example cannot become an untouched evaluation case.

## Public-only engineering replay

The fixed `json_current` artifact for every one of the twelve bugs was replayed
with the existing public suite. Choosing that format is an engineering convention;
it did not meet the prior calibration gate. No evaluator outcome selects a probe.

- **12/12 candidates retained.**
- **8** have a public failure; all eight yield an available trace with the same
  observed result as the original public check and an ordinary re-execution.
- **4** pass public tests, so the adapter emits `no_public_failure`. These include
  the three false-positive bugs above and the genuinely full-suite-passing
  youtube-dl/32 candidate. The adapter does not claim it can distinguish them.
- **16 additional local executions**, plus the initial public checks and sandbox
  preflight. Wall times are saved; no API call or dollar charge was incurred.

Traces and three inert request hashes are saved, with the exact new source
hashes. The raw and focused controls have the same available facts; the trace
arm adds intermediate states. No requests were sent to a model. This demonstrates
information-boundary engineering, not improved repairs, a learned policy, or
statistical action complementarity.

From repository root:

```bash
.venv/bin/python experiments/python-repair/checkpoint-environment/results/diagnostic-audit-20261026/reproduce.py \
  --output runs/diagnostic-case-audit.json

.venv/bin/python experiments/python-repair/checkpoint-environment/results/diagnostic-audit-20261026/reproduce.py \
  --trace-public --output runs/diagnostic-trace-replay.json
```

The first command only reads inert archived evidence. The second requires macOS
`sandbox-exec` and executes saved candidates under the existing OS isolation;
there is no unrestricted fallback. Use fresh output paths. Reproductions compare
exactly after removing measured `verifier_seconds` and `diagnostic_seconds`;
the environment's recorded Python version can differ across hosts.

The bounded tracer is diagnostic instrumentation, not a security attestation:
candidate behavior can depend on tracing, locals are candidate data, and a
finite consistent execution is not proof of general correctness. Mismatches,
timeouts and disabled tracing are explicitly unavailable and must remain in
future analyses.
