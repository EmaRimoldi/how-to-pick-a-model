# Cross-benchmark recovery replication

Prospective external-task replication of the HumanEval+ context-value study.
This bundle is a focused extension of the retained edit/verify experiment, not
a restoration of the former MBPP scaffolding.

The previous HumanEval+ evaluation has been observed. All its 51 failed
checkpoints are now explicitly **training data** for a new MBPP+ holdout. No
HumanEval+ score is relabelled as new evidence. The new primary comparison asks
whether artifact features improve decisions beyond public verifier feedback.

Read [PROTOCOL.md](PROTOCOL.md) before collection or interpretation. Collection
is opt-in, needs macOS isolation and optional EvalPlus, and shares the previously
approved cumulative $2 ceiling. Planning and offline analysis never call models.

Collection is finished and the [audited evidence](results/replication-20261022/README.md)
is available. It contains 2,878 recovery responses, two censored solver cells,
94/96 complete selected failure states, and all 288 prespecified API forecasts.
The protocol, reference census, frozen configuration and weights preceded live
calls. Transport censoring and the disclosed continuation after a partial audit
mean complete-case intervals remain **descriptive**.

For 9B, feedback alone succeeds 52.8% versus 30.9% with feedback plus failed
code. For 27B the rates are 62.4% and 58.5%. The direct model interaction is
-18.1 percentage points, nominal family-adjusted interval [-31.6,-5.3]. The
primary artifact-feature selector advantage is not established: +$0.00011119
per failure, descriptive 95% interval [-$0.00042595,+$0.00064848]. Missing-state
bounds for all 96 selected failures also span zero. The API semantic control
does not establish an artifact-information gain either.

Read the [full report](results/replication-20261022/report.md) and the
[separate empirical paper](../../../paper/recovery-value/README.md).
Cumulative known charges and every reservation total $1.39600335, below the
unchanged $2 ceiling. Offline replay requires no credentials, GPUs or model calls.

Pre-call reference census: 377/378 tasks compatible; `Mbpp/599` is excluded
because its canonical implementation exceeds the full-suite verifier limit.
All 378 base reference checks passed. The config and policy are committed before
model calls.

After recovery collection encountered a transport failure, an explicit human
exception authorized only the 1,466 requests never admitted before that stop.
Read the final protocol addendum and
[authorization freeze](configs/recovery-continuation-freeze.json). Known and
uncertain requests are never repeated; original prediction and journal bytes are
preserved. This does not turn the censored bank into a completed confirmatory test.

An explicit continuation can be inspected without model calls:

```bash
python -m vao.decisions.transfer_continuation \
  --source runs/mbpp-recovery-transfer-continuation-20261022 \
  --freeze experiments/mbpp-plus/context-value-transfer/configs/recovery-continuation-freeze.json \
  --output runs/mbpp-unadmitted-plan
```

This is planning only. Live collection additionally requires `--live`,
`--key-stdin` and the existing cumulative `--budget-usd 1.48`, with all imported
charges and unresolved reservations included.

These are historical collection commands: each continuation requires the exact
collector version recorded in its authorization freeze. A post-collection fix
now preserves a transport error over sibling shutdown errors in summary status;
it does not change the archived collectors, frozen configs or observed evidence.
Use the recorded Git version for historical planning. Current offline replay
and the paper build require no historical checkout or new collection.

The [second recovery continuation freeze](configs/recovery-continuation-segment2-freeze.json)
contains 433 remaining cells after another transport stop. They are a subset of
the same original 1,466-cell human authorization. Prior lineage files, preflights
and stop summaries are archived before any new segment; two solver cells remain
censored and the complete-case interpretation stays descriptive.

```bash
python scripts/run_recovery_transfer.py \
  --config experiments/mbpp-plus/context-value-transfer/configs/replication.json \
  --output runs/mbpp-recovery-plan
```

This defaults to planning only. Live collection additionally requires explicit
`--live --budget-usd 1.48 --key-stdin` and the optional EvalPlus environment.

The [public-spec audit](data/public-spec-audit.json) additionally checks every
prompt's assertion against the reference, with no Plus input. All 378 pass.
Reproduce it with the optional environment on macOS:

```bash
python experiments/mbpp-plus/context-value-transfer/source/audit_public_spec.py \
  --output runs/mbpp-public-spec-audit.json
```

This runs trusted benchmark references in the OS sandbox, with no model calls.

## Data attribution

MBPP originates from Google Research and Austin et al.,
[Program Synthesis with Large Language Models](https://arxiv.org/abs/2108.07732).
Its [dataset card](https://huggingface.co/datasets/google-research-datasets/mbpp)
identifies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
This study uses EvalPlus's reformatted MBPP+ prompts and adds sampled model
outputs, public-verifier feedback and cost/outcome annotations. Original benchmark
material retains its upstream attribution and licensing.
The [EvalPlus implementation](https://github.com/evalplus/evalplus/tree/v0.3.1)
uses Apache 2.0, with an additional HumanEval MIT notice for its checker files.
