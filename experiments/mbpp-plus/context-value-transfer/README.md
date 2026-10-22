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

The protocol, reference census, frozen configuration and weights must be saved
and committed before live calls. Results and a reproduction command will be
linked here after auditing the collected journal. A prospective design is not a
completed result or a guarantee of a publishable method improvement.

Pre-call reference census: 377/378 tasks compatible; `Mbpp/599` is excluded
because its canonical implementation exceeds the full-suite verifier limit.
All 378 base reference checks passed. The config and policy are committed before
model calls.

```bash
python scripts/run_recovery_transfer.py \
  --config experiments/mbpp-plus/context-value-transfer/configs/replication.json \
  --output runs/mbpp-recovery-plan
```

This defaults to planning only. Live collection additionally requires explicit
`--live --budget-usd 1.48 --key-stdin` and the optional EvalPlus environment.
