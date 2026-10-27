# Function-balanced trace retention: offline engineering evidence

An opt-in sampler retains execution events across function definitions instead
of keeping only the final events. It recovers the previously omitted composition
method in both failing Scrapy/26 examples. **This is coverage evidence, not a
measured improvement in model repair or a validated acquisition policy.**

## Compared inputs and measurements

Every already-published input is retained: four engineering examples from
Scrapy/26 and all six public cases from each of the six broader development
adapters, on both buggy and fixed artifacts. That is **80 case/variant
comparisons across seven development bugs**; no held-out or evaluator input is
used. Fixed artifacts are independent engineering controls. Their content and
correctness are never inputs to event selection in a buggy execution.

Each case is executed ordinarily, with the historical tail trace and with the
new trace, three times with rotated execution order. A second fresh run repeats
the full bank. Each bank has **720 sandbox executions**, plus one isolation
preflight. This is 80 correlated case/variant comparisons, not 720 independent
bugs or model attempts. Both runs make **zero API calls**.

| Recorded property | Initial bank | Fresh second bank |
| --- | ---: | ---: |
| Ordinary/tail/new observations agree | 240/240 | 240/240 |
| Both trace modes available | 80/80 | 80/80 |
| New trace covers more / same / fewer function names | 12 / 68 / 0 | 12 / 68 / 0 |
| Failing Scrapy/26 examples retain `_getcomposite`, tail → new | 0/2 → 2/2 | 0/2 → 2/2 |
| Capture or buffer ceiling reached | 0 | 0 |
| Cases with differing trace values across repeats | 2/80 | 2/80 |

The changed method is used only for this post-execution audit; no fault
annotation is supplied to the sampler. More represented function names does not
mean more information at every line: allocating events across functions can
lose detail within any one function. Definition-line identities distinguish
same-named methods; the table uses names for compatibility with the old trace,
which has no definition-line field. The sampler does not distinguish individual
recursive invocations.

In the second run, summed wall time over 240 invocations was 13.51 s ordinarily,
16.64 s with the tail trace and 18.37 s with the balanced trace. Respective
medians were 43.19, 77.63 and 79.90 ms. These measurements include process startup
on one host; they are not an isolated tracer benchmark, an API price, a peak-memory
measurement or an equal-total-budget policy comparison. Raw timings and rotated
orders remain in [report.json](report.json).

## Selection and bounds

`RegionRepairVerifier` is an explicit opt-in; existing collectors and their
historical verifier/worker files are unchanged. Its standalone worker captures
at most 512 candidate line/return/exception events with at most 1 MiB of summed
serialized event bytes. This byte bound does not bound Python object overhead
or total process memory. Values use the exact historical bounded compactor,
without calling candidate representation methods or attribute getters.

Events are grouped by file, function definition line and function name, in first
execution order. Round-robin selection considers each function's final captured
event, first exception, initial event, then recursive temporal midpoints. It
emits at most 32 events and 12,000 summed serialized event bytes, chronologically
ordered with original event sequence numbers. An event is copied unchanged;
missing steps must not be read as adjacent execution. More than 32 functions or
large events can leave functions unrepresented, recorded in omission metadata.
The parent checks bounds and accounting. Diagnostic candidate data remains
untrusted and never supplies a correctness flag.

The input is the current candidate and public call arguments. Expected answers,
reference code and evaluator cases never enter the worker. The compatibility
inventory is taken before importing the candidate inside the existing OS
sandbox. Tests cover two-module tracing, exact compact values, event/capture/byte
limits, malformed metadata, unavailable traces, timeouts, invalid output and
tracing disabled by a candidate.

## Limits discovered and retained

**Object state remains omitted.** The recovered `_getcomposite` events contain
useful location/name context, but `self` and the composed settings object are
still represented as omitted objects. Other retained functions expose some
primitive locals. Function coverage alone does not demonstrate that the model
can see the state needed for a repair. We did not add unsafe object introspection
or change the value codec after observing this limit.

**Trace byte identity is not repeatable in two ordering cases.** Both buggy and
fixed The Fuck/22 ordering cases contain varying hash returns and, in some
repeats, different intermediate set iteration values. Ordinary and traced final
observations remain identical. A [separate benign interpreter probe](hash-isolation-probe.json)
confirms that `python -I` ignores the supplied `PYTHONHASHSEED`; the candidate
also hashes `(script, side_effect)`. This is not a complete causal decomposition
of every differing intermediate value. The historical sandbox remains unchanged.
No hash or set observation was normalized, omitted from results or relabeled
deterministic.

The initial probe returned a nonzero status because it initially required exact
trace equality across repeats. Its full [report](initial-report.json), archive
and changed [probe source](initial-source/scripts__probe_repair_trace_retention.py.txt)
are preserved. The final probe distinguishes stable observed results from
stochastic trace values and checks **every** replicate's observation agreement.
It also adds rejection of malformed filename metadata. The second run uses this
revised audit; the sampler itself is unchanged between banks. The explicit trace
nondeterminism fields remain false/marked in both reports.

This mode is **not connected to paid collection**. Before a model study, decide
whether retained built-in state is sufficient on the selected development
checkpoints and specify how an actually acquired stochastic trace is frozen,
bound to its workspace and public input, and charged. Re-executing a trace and
requiring identical bytes is not a valid generic acquisition check. A future
study must keep baseline code/feedback identical, report all selected failures,
and test repair benefit; no selector training is justified by this probe.

## Reproduction

From the repository root, audit both saved banks without executing candidates:

```bash
uv run python experiments/python-repair/checkpoint-environment/results/trace-retention-20261027/reproduce_analysis.py
```

The [saved audit](reverification.json) verifies both archive hashes, all fifteen
runtime/input identities from inert source blobs, every saved observation comparison, event bounds and
descriptive function coverage. Ordinary observations agree between banks. It
does not claim byte-identical stochastic traces or model efficacy. Add
`--check-current-sources` to also check the working checkout against the
recorded runtime; the default historical audit does not require future code
to remain identical. Source blobs are validated as data and never executed.

To run a new native sandbox comparison, use a fresh output directory:

```bash
uv run python scripts/probe_repair_trace_retention.py \
  --output runs/trace-retention-fresh --repeats 3
```

The script validates adapter identities against the original published probe
and inert pool sources before execution. All trace records, including omissions
and varying values, are stored in compressed inert JSON. A new run can vary in
wall time, hashes and intermediate set order. Every prior bank remains immutable.

- Initial archive SHA-256: `2747fa7ee05d52947dc12463da69629839abaa91b62755f373c50f59b61f44e2`.
- Second archive SHA-256: `4946f1d37e44e0a27d66de0512bd8acbeecce0d2a68bc91619bc65b69650be62`.

Runtime trace compression and routing have existing precedents; see the
[prior literature discussion](../stateful-trace-feasibility-20261027/README.md).
No novelty, scaling, model-benefit or held-out generalization claim follows here.
