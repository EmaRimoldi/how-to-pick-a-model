# Strategy by Difficulty Grid on HumanEval+

The completed run `full-20260711T201122Z` evaluates model/strategy combinations
and preserves raw shards, router decisions, exact config/source snapshots,
derived validation and accounting summaries, and four PDF figures.

The 24 accepted worker shards contain 1,476 complete model/strategy/task cells.
Scheduler stdout/stderr and the cancelled partial shard from `node3614` are
archived in [repository history](../../../docs/history-merge.md). The cancelled
shard was quarantined outside the analysis input directory and is not part of
the recorded complete bank. Run IDs, amendments, job metadata, source/config
snapshots and the completeness report remain with the accepted data.

Use `scripts/submit_strategy_full.sh` for a new cluster run. It writes all new
artifacts under this bundle's `runs/<run-id>/` directory.
