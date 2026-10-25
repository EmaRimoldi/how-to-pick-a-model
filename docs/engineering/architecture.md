# Runtime and evidence architecture

The maintained package covers seven coding-task studies on HumanEval+, MBPP+
and BigCodeBench. Collection and analysis of recorded evidence are separate.

```text
frozen tasks + protocol + model/budget settings
  -> vao.decisions collector
  -> provider receipts + budget journal + public verification + evaluator labels
  -> immutable evidence + collection-source snapshots
  -> scripts/analyze_* and verify_feedback_evidence.py
  -> audited comparisons, reports and paper inputs
```

## Shared implementation

`vao.decisions.openrouter` owns provider accounting and conservative reservations.
`verification.py` and `bigcode.py` isolate candidate execution and separate public
feedback from evaluator-only labels. Unknown admissions remain reserved and are
never silently retried. A public pass ends a feedback-only trajectory even when
hidden tests subsequently fail.

HumanEval+ checkpoint, recovery, MBPP+ transfer and BigCodeBench collectors remain
separate where interventions, task splits or budgets differ. They share transport,
accounting and verification primitives. The general multi-step controller remains
future work. Root `src/*.py` modules own the older HumanEval+ worker/frontier,
retry-allocation, strategy and router-context analyses.

## Evidence and provenance

`experiments/` retains protocols, frozen configurations, receipts and the original
outcomes, including negative and censored results. Inert collection-source
snapshots are intentional provenance. Offline audits hash those snapshots and
reconstruct prompt chains and statistics with maintained analysis code.

Live collection additionally requires a reviewed freeze matching the current
sources. Completed campaigns must not be resumed. Current plan-only commands
make no provider call; source drift prevents execution under an old freeze.

CIFAR-10 experiments and the legacy `agent-workflow`/CIFAR-10 harness are archived
in [repository history](../history-merge.md). Historical manuscripts keep their
embedded figures for compilation. Their scientific claims and limitations are
not changed by retiring the reproduction surface.

Use [reproducibility](../reproducibility.md) for installation and saved-data
replays. `make check` refreshes navigation, validates links, compiles source and
runs the offline suite. CI also audits the three recorded recovery/policy banks.
