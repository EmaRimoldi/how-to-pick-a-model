"""Candidate engines for the stateful query benchmark."""

from benchmarks.stateful_query_engine.candidate.engine import BaselineQueryEngine
from benchmarks.stateful_query_engine.candidate.optimized_engine import OptimizedQueryEngine
from benchmarks.stateful_query_engine.candidate.variants import (
    CANDIDATE_REGISTRY,
    BuggyTieBreakEngine,
    DictScanQueryEngine,
    FenwickRangeQueryEngine,
    HotGetCacheQueryEngine,
    PrefixRebuildQueryEngine,
    RangeCacheQueryEngine,
)

__all__ = [
    "BaselineQueryEngine",
    "OptimizedQueryEngine",
    "DictScanQueryEngine",
    "PrefixRebuildQueryEngine",
    "RangeCacheQueryEngine",
    "FenwickRangeQueryEngine",
    "HotGetCacheQueryEngine",
    "BuggyTieBreakEngine",
    "CANDIDATE_REGISTRY",
]
