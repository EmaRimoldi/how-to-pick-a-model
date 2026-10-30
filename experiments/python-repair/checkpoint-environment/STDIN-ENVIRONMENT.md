# Whole-program stdin/stdout execution

`vao.repair.stdin_verifier.StdinVerifier` is an offline engineering backend for
unchanged Python source bytes. It does not launch model calls or define a FixEval
cohort, suite split, success criterion or authorized allocation.

Each invocation creates a fresh macOS sandbox and immutable source directory.
The program runs as `__main__` with its own filename in `argv[0]`; input bytes are
sent unchanged to stdin, including leading/trailing whitespace, newlines and binary
values. Source bytes retain their encoding declaration. No expected output, other
test input, reference code, provenance or inherited credentials enters the child.
The current interpreter version is recorded: this is not an emulation of historical
CPython 3.4/3.8, and incompatibilities must remain recorded qualification failures.

Standard output and error are bounded regular files and returned as base64, without
normalization. The parent scores outputs using an explicitly selected comparator:
exact bytes or ASCII-whitespace-separated byte tokens. Neither permits approximate
numeric matching. A nonzero exit, timeout or output limit always fails, even if its
partial output matches. The appropriate comparator must be frozen for the actual
problem specifications before qualification; no default is silently assumed.

The backend denies network and private-file access, denies all source writes and
metadata changes, allows isolated scratch writes, removes descendants on exit and
sets CPU, output-file and descriptor limits (2 seconds, 128 KiB, 64 descriptors).
The wall timeout is explicit. There is no separately validated hard resident-memory
limit in this backend. It fails closed on unsupported hosts; Linux CI tests the
portable comparison contract and skips native execution.

Optional `stdin-main-line-coverage-v1` records main-thread line execution from
module startup through exit, bounded at 100,000 events / 4,096 locations. It is
distinct from the older function-entrypoint coverage schema. Disabled tracing,
missing/malformed reports, unsupported source decoding or exhausted coverage limits
remain unavailable diagnostics. Coverage is not a pass flag. A study must compare
ordinary and covered outputs before accepting any diagnostic observation, and must
count both executions. Threaded/child-process coverage is not claimed.

Synthetic tests verify binary stdin preservation, real main/exit semantics,
ordinary/covered agreement, source/private-file/network denial, fresh scratch state,
timeouts, output limits, tracing disabled by a program and parent-side scoring.
No real dataset program has been qualified by these engineering tests.

## Opt-in monitoring coverage

`MonitoringStdinVerifier` retains ordinary execution through the unchanged backend
and uses CPython 3.12+ `sys.monitoring` for covered executions. It emits the distinct
`stdin-monitoring-line-coverage-v1` schema. Returning `DISABLE` after a LINE callback
records presence without paying for every repeated loop visit; callback counts
therefore have a different meaning from legacy trace-event counts. Location and
callback limits, missing-report handling and ordinary/covered agreement checks
still apply. No thread/process coverage or adversarial tamper resistance is claimed.

The [complete comparison on eleven qualified programs](results/stdin-ablation-preparation-20261030/README.md)
preserves both banks and verifies 82 ordinary outcomes, 82 monitoring/ordinary
pairs, 60 legacy-complete line sets and all F/N/S projections. One diagnostic
remains unavailable; empty and flat results are retained. This validates an
environmental mechanism, not diagnostic value for model repair.
