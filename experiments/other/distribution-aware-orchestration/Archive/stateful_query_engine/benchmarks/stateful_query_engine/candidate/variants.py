"""Additional candidate variants for multi-step search experiments."""

from __future__ import annotations

import bisect
import heapq

from benchmarks.stateful_query_engine.candidate.engine import BaselineQueryEngine
from benchmarks.stateful_query_engine.candidate.optimized_engine import OptimizedQueryEngine


class DictScanQueryEngine:
    """Dictionary layout: fast point lookups, linear range scans."""

    def __init__(self, items: dict[int, int] | None = None):
        self._values = {int(key): int(value) for key, value in (items or {}).items()}

    def put(self, key: int, value: int) -> None:
        self._values[int(key)] = int(value)
        return None

    def delete(self, key: int) -> None:
        self._values.pop(int(key), None)
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(value for key, value in self._values.items() if lo <= key <= hi)

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        return sum(1 for key in self._values if lo <= key <= hi)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        rows = [(key, value) for key, value in self._values.items() if lo <= key <= hi]
        return sorted(rows, key=lambda item: (-item[1], item[0]))[:k]


class PrefixRebuildQueryEngine:
    """Correct but p95-hostile variant that rebuilds prefix sums after writes."""

    def __init__(self, items: dict[int, int] | None = None):
        self._values = {int(key): int(value) for key, value in (items or {}).items()}
        self._keys = sorted(self._values)
        self._prefix = [0]
        self._dirty = True

    def put(self, key: int, value: int) -> None:
        key = int(key)
        if key not in self._values:
            bisect.insort(self._keys, key)
        self._values[key] = int(value)
        self._dirty = True
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        if key not in self._values:
            return None
        del self._values[key]
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
        self._dirty = True
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        if left >= right:
            return 0
        self._ensure_prefix()
        return self._prefix[right] - self._prefix[left]

    def aggregate_count(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        return max(0, right - left)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        k = int(k)
        left, right = self._range_bounds(lo, hi)
        if left >= right or k <= 0:
            return []
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        return bisect.bisect_left(self._keys, lo), bisect.bisect_right(self._keys, hi)

    def _ensure_prefix(self) -> None:
        if not self._dirty:
            return
        total = 0
        prefix = [0]
        for key in self._keys:
            total += self._values[key]
            prefix.append(total)
        self._prefix = prefix
        self._dirty = False


class RangeCacheQueryEngine(OptimizedQueryEngine):
    """Sorted index plus exact range-result cache with conservative invalidation."""

    def __init__(self, items: dict[int, int] | None = None):
        super().__init__(items)
        self._cache: dict[tuple, object] = {}

    def put(self, key: int, value: int) -> None:
        self._cache.clear()
        return super().put(key, value)

    def delete(self, key: int) -> None:
        self._cache.clear()
        return super().delete(key)

    def range_sum(self, lo: int, hi: int) -> int:
        cache_key = ("sum", int(lo), int(hi))
        if cache_key not in self._cache:
            self._cache[cache_key] = super().range_sum(lo, hi)
        return int(self._cache[cache_key])

    def aggregate_count(self, lo: int, hi: int) -> int:
        cache_key = ("count", int(lo), int(hi))
        if cache_key not in self._cache:
            self._cache[cache_key] = super().aggregate_count(lo, hi)
        return int(self._cache[cache_key])

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        cache_key = ("top_k", int(lo), int(hi), int(k))
        if cache_key not in self._cache:
            self._cache[cache_key] = super().top_k(lo, hi, k)
        return list(self._cache[cache_key])


class HotGetCacheQueryEngine(DictScanQueryEngine):
    """Point-lookup cache variant; usually a decoy because dict lookup is already O(1)."""

    def __init__(self, items: dict[int, int] | None = None):
        super().__init__(items)
        self._get_cache: dict[int, int | None] = {}

    def put(self, key: int, value: int) -> None:
        self._get_cache.pop(int(key), None)
        return super().put(key, value)

    def delete(self, key: int) -> None:
        self._get_cache.pop(int(key), None)
        return super().delete(key)

    def get(self, key: int) -> int | None:
        key = int(key)
        if key not in self._get_cache:
            self._get_cache[key] = super().get(key)
        return self._get_cache[key]


class LazySortedQueryEngine:
    """Dictionary plus lazily rebuilt sorted-key index after write bursts."""

    def __init__(self, items: dict[int, int] | None = None):
        self._values = {int(key): int(value) for key, value in (items or {}).items()}
        self._keys: list[int] = []
        self._dirty = True

    def put(self, key: int, value: int) -> None:
        self._values[int(key)] = int(value)
        self._dirty = True
        return None

    def delete(self, key: int) -> None:
        self._values.pop(int(key), None)
        self._dirty = True
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        if left >= right:
            return 0
        return sum(self._values[key] for key in self._keys[left:right])

    def aggregate_count(self, lo: int, hi: int) -> int:
        left, right = self._range_bounds(lo, hi)
        return max(0, right - left)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        left, right = self._range_bounds(lo, hi)
        k = int(k)
        if left >= right or k <= 0:
            return []
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        self._ensure_keys()
        return bisect.bisect_left(self._keys, lo), bisect.bisect_right(self._keys, hi)

    def _ensure_keys(self) -> None:
        if self._dirty:
            self._keys = sorted(self._values)
            self._dirty = False


class SnapshotSortQueryEngine(DictScanQueryEngine):
    """Correct query-time sorted snapshot; intentionally hostile to repeated ranges."""

    def _keys_in_range(self, lo: int, hi: int) -> list[int]:
        if lo > hi:
            return []
        return [key for key in sorted(self._values) if lo <= key <= hi]

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        return sum(self._values[key] for key in self._keys_in_range(lo, hi))

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        return len(self._keys_in_range(lo, hi))

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        k = int(k)
        if k <= 0:
            return []
        lo = int(lo)
        hi = int(hi)
        rows = [(key, self._values[key]) for key in self._keys_in_range(lo, hi)]
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))


class SumCacheQueryEngine(OptimizedQueryEngine):
    """Sorted index with range-sum cache only."""

    def __init__(self, items: dict[int, int] | None = None):
        super().__init__(items)
        self._sum_cache: dict[tuple[int, int], int] = {}

    def put(self, key: int, value: int) -> None:
        self._sum_cache.clear()
        return super().put(key, value)

    def delete(self, key: int) -> None:
        self._sum_cache.clear()
        return super().delete(key)

    def range_sum(self, lo: int, hi: int) -> int:
        cache_key = (int(lo), int(hi))
        if cache_key not in self._sum_cache:
            self._sum_cache[cache_key] = super().range_sum(lo, hi)
        return self._sum_cache[cache_key]


class TopKCacheQueryEngine(OptimizedQueryEngine):
    """Sorted index with top-k cache only."""

    def __init__(self, items: dict[int, int] | None = None):
        super().__init__(items)
        self._top_cache: dict[tuple[int, int, int], list[tuple[int, int]]] = {}

    def put(self, key: int, value: int) -> None:
        self._top_cache.clear()
        return super().put(key, value)

    def delete(self, key: int) -> None:
        self._top_cache.clear()
        return super().delete(key)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        cache_key = (int(lo), int(hi), int(k))
        if cache_key not in self._top_cache:
            self._top_cache[cache_key] = super().top_k(lo, hi, k)
        return list(self._top_cache[cache_key])


class BucketSummaryQueryEngine:
    """Bucketed sum/count summaries with exact edge scans and exact top-k fallback."""

    bucket_width = 1024

    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {}
        self._bucket_sums: dict[int, int] = {}
        self._bucket_counts: dict[int, int] = {}
        self._keys: list[int] = []
        for key, value in (items or {}).items():
            self.put(int(key), int(value))

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        old = self._values.get(key)
        if old is None:
            bisect.insort(self._keys, key)
            self._bucket_counts[self._bucket(key)] = self._bucket_counts.get(self._bucket(key), 0) + 1
            old = 0
        self._values[key] = value
        bucket = self._bucket(key)
        self._bucket_sums[bucket] = self._bucket_sums.get(bucket, 0) + value - old
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        old = self._values.pop(key, None)
        if old is None:
            return None
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
        bucket = self._bucket(key)
        self._bucket_sums[bucket] = self._bucket_sums.get(bucket, 0) - old
        self._bucket_counts[bucket] = self._bucket_counts.get(bucket, 0) - 1
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        first_bucket = self._bucket(lo)
        last_bucket = self._bucket(hi)
        if first_bucket == last_bucket:
            return sum(value for key, value in self._values.items() if lo <= key <= hi)
        total = 0
        first_end = (first_bucket + 1) * self.bucket_width - 1
        last_start = last_bucket * self.bucket_width
        total += sum(value for key, value in self._values.items() if lo <= key <= first_end)
        total += sum(value for key, value in self._values.items() if last_start <= key <= hi)
        for bucket in range(first_bucket + 1, last_bucket):
            total += self._bucket_sums.get(bucket, 0)
        return total

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        first_bucket = self._bucket(lo)
        last_bucket = self._bucket(hi)
        if first_bucket == last_bucket:
            return sum(1 for key in self._values if lo <= key <= hi)
        total = 0
        first_end = (first_bucket + 1) * self.bucket_width - 1
        last_start = last_bucket * self.bucket_width
        total += sum(1 for key in self._values if lo <= key <= first_end)
        total += sum(1 for key in self._values if last_start <= key <= hi)
        for bucket in range(first_bucket + 1, last_bucket):
            total += self._bucket_counts.get(bucket, 0)
        return total

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        left = bisect.bisect_left(self._keys, lo)
        right = bisect.bisect_right(self._keys, hi)
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def _bucket(self, key: int) -> int:
        return int(key) // self.bucket_width


class BucketSummarySmallQueryEngine(BucketSummaryQueryEngine):
    bucket_width = 128


class BucketSummaryWideQueryEngine(BucketSummaryQueryEngine):
    bucket_width = 4096


class StaleRangeCacheBugEngine(RangeCacheQueryEngine):
    """Incorrect decoy: fails to invalidate exact range cache after writes."""

    def put(self, key: int, value: int) -> None:
        return OptimizedQueryEngine.put(self, key, value)

    def delete(self, key: int) -> None:
        return OptimizedQueryEngine.delete(self, key)


class MissingDeleteBugEngine(OptimizedQueryEngine):
    """Incorrect decoy: ignores delete operations."""

    def delete(self, key: int) -> None:
        return None


class ExclusiveHiBugEngine(OptimizedQueryEngine):
    """Incorrect decoy: treats upper range bounds as exclusive."""

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        return bisect.bisect_left(self._keys, lo), bisect.bisect_left(self._keys, hi)


class FenwickRangeQueryEngine:
    """Dynamic Fenwick summaries for range sum/count plus sorted-key top-k fallback."""

    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {}
        max_key = max((int(key) for key in (items or {})), default=0)
        self._size = max(16, max_key + 2)
        self._sum_tree = [0] * (self._size + 1)
        self._count_tree = [0] * (self._size + 1)
        self._keys: list[int] = []
        for key, value in (items or {}).items():
            self.put(int(key), int(value))

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        self._ensure_size(key + 2)
        old = self._values.get(key)
        if old is None:
            bisect.insort(self._keys, key)
            self._add(self._count_tree, key + 1, 1)
            old = 0
        self._values[key] = value
        self._add(self._sum_tree, key + 1, value - old)
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        old = self._values.pop(key, None)
        if old is None:
            return None
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
        self._add(self._sum_tree, key + 1, -old)
        self._add(self._count_tree, key + 1, -1)
        return None

    def get(self, key: int) -> int | None:
        return self._values.get(int(key))

    def range_sum(self, lo: int, hi: int) -> int:
        lo = max(0, int(lo))
        hi = int(hi)
        if lo > hi:
            return 0
        self._ensure_size(hi + 2)
        return self._prefix(self._sum_tree, hi + 1) - self._prefix(self._sum_tree, lo)

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = max(0, int(lo))
        hi = int(hi)
        if lo > hi:
            return 0
        self._ensure_size(hi + 2)
        return self._prefix(self._count_tree, hi + 1) - self._prefix(self._count_tree, lo)

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        left = bisect.bisect_left(self._keys, lo)
        right = bisect.bisect_right(self._keys, hi)
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def _ensure_size(self, minimum: int) -> None:
        if minimum <= self._size:
            return
        old_values = dict(self._values)
        while self._size < minimum:
            self._size *= 2
        self._sum_tree = [0] * (self._size + 1)
        self._count_tree = [0] * (self._size + 1)
        for key, value in old_values.items():
            self._add(self._sum_tree, key + 1, value)
            self._add(self._count_tree, key + 1, 1)

    def _add(self, tree: list[int], index: int, delta: int) -> None:
        while index <= self._size:
            tree[index] += delta
            index += index & -index

    def _prefix(self, tree: list[int], index: int) -> int:
        index = min(index, self._size)
        total = 0
        while index > 0:
            total += tree[index]
            index -= index & -index
        return total


class BuggyTieBreakEngine(BaselineQueryEngine):
    """Intentionally incorrect candidate used to validate correctness gating."""

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        rows = super().top_k(lo, hi, k)
        return sorted(rows, key=lambda item: (-item[1], -item[0]))


CANDIDATE_REGISTRY = {
    "baseline": {
        "factory": BaselineQueryEngine,
        "file": "candidate/engine.py",
        "mode": "other",
        "description": "list-backed baseline",
    },
    "dict_scan": {
        "factory": DictScanQueryEngine,
        "file": "candidate/variants.py",
        "mode": "layout",
        "description": "dictionary layout with linear range scans",
    },
    "prefix_rebuild": {
        "factory": PrefixRebuildQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "lazy full prefix rebuild after writes",
    },
    "sorted_range": {
        "factory": OptimizedQueryEngine,
        "file": "candidate/optimized_engine.py",
        "mode": "indexing",
        "description": "ordered keys with narrow range slicing",
    },
    "optimized": {
        "factory": OptimizedQueryEngine,
        "file": "candidate/optimized_engine.py",
        "mode": "indexing",
        "description": "alias for sorted_range",
    },
    "range_cache": {
        "factory": RangeCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "ordered keys plus range-result cache",
    },
    "hot_get_cache": {
        "factory": HotGetCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "point-lookup cache decoy",
    },
    "fenwick_range": {
        "factory": FenwickRangeQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "dynamic Fenwick range sum/count summaries with sorted top-k fallback",
    },
    "buggy_tie": {
        "factory": BuggyTieBreakEngine,
        "file": "candidate/variants.py",
        "mode": "other",
        "description": "incorrect top_k tie-breaking",
    },
    "branch_00": {
        "factory": BaselineQueryEngine,
        "file": "candidate/engine.py",
        "mode": "other",
        "description": "masked hard-search branch 00",
    },
    "branch_01": {
        "factory": HotGetCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 01",
    },
    "branch_02": {
        "factory": StaleRangeCacheBugEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 02",
    },
    "branch_03": {
        "factory": SnapshotSortQueryEngine,
        "file": "candidate/variants.py",
        "mode": "layout",
        "description": "masked hard-search branch 03",
    },
    "branch_04": {
        "factory": DictScanQueryEngine,
        "file": "candidate/variants.py",
        "mode": "layout",
        "description": "masked hard-search branch 04",
    },
    "branch_05": {
        "factory": BucketSummarySmallQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 05",
    },
    "branch_06": {
        "factory": MissingDeleteBugEngine,
        "file": "candidate/variants.py",
        "mode": "indexing",
        "description": "masked hard-search branch 06",
    },
    "branch_07": {
        "factory": LazySortedQueryEngine,
        "file": "candidate/variants.py",
        "mode": "indexing",
        "description": "masked hard-search branch 07",
    },
    "branch_08": {
        "factory": PrefixRebuildQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 08",
    },
    "branch_09": {
        "factory": SumCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 09",
    },
    "branch_10": {
        "factory": ExclusiveHiBugEngine,
        "file": "candidate/variants.py",
        "mode": "indexing",
        "description": "masked hard-search branch 10",
    },
    "branch_11": {
        "factory": TopKCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 11",
    },
    "branch_12": {
        "factory": BucketSummaryQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 12",
    },
    "branch_13": {
        "factory": BuggyTieBreakEngine,
        "file": "candidate/variants.py",
        "mode": "other",
        "description": "masked hard-search branch 13",
    },
    "branch_14": {
        "factory": BucketSummaryWideQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 14",
    },
    "branch_15": {
        "factory": RangeCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 15",
    },
    "branch_16": {
        "factory": PrefixRebuildQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 16",
    },
    "branch_17": {
        "factory": FenwickRangeQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 17",
    },
    "branch_18": {
        "factory": SnapshotSortQueryEngine,
        "file": "candidate/variants.py",
        "mode": "layout",
        "description": "masked hard-search branch 18",
    },
    "branch_19": {
        "factory": OptimizedQueryEngine,
        "file": "candidate/optimized_engine.py",
        "mode": "indexing",
        "description": "masked hard-search branch 19",
    },
    "branch_20": {
        "factory": SumCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 20",
    },
    "branch_21": {
        "factory": StaleRangeCacheBugEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 21",
    },
    "branch_22": {
        "factory": LazySortedQueryEngine,
        "file": "candidate/variants.py",
        "mode": "indexing",
        "description": "masked hard-search branch 22",
    },
    "branch_23": {
        "factory": BucketSummaryQueryEngine,
        "file": "candidate/variants.py",
        "mode": "summaries",
        "description": "masked hard-search branch 23",
    },
    "branch_24": {
        "factory": DictScanQueryEngine,
        "file": "candidate/variants.py",
        "mode": "layout",
        "description": "masked hard-search branch 24",
    },
    "branch_25": {
        "factory": TopKCacheQueryEngine,
        "file": "candidate/variants.py",
        "mode": "caching",
        "description": "masked hard-search branch 25",
    },
    "branch_26": {
        "factory": OptimizedQueryEngine,
        "file": "candidate/optimized_engine.py",
        "mode": "indexing",
        "description": "masked hard-search branch 26",
    },
    "branch_27": {
        "factory": MissingDeleteBugEngine,
        "file": "candidate/variants.py",
        "mode": "indexing",
        "description": "masked hard-search branch 27",
    },
}


_EXTRA_HARD_BRANCH_FACTORIES = [
    (BaselineQueryEngine, "other"),
    (MissingDeleteBugEngine, "indexing"),
    (HotGetCacheQueryEngine, "caching"),
    (SnapshotSortQueryEngine, "layout"),
    (StaleRangeCacheBugEngine, "caching"),
    (DictScanQueryEngine, "layout"),
    (ExclusiveHiBugEngine, "indexing"),
    (PrefixRebuildQueryEngine, "summaries"),
    (StaleRangeCacheBugEngine, "caching"),
    (SumCacheQueryEngine, "caching"),
    (MissingDeleteBugEngine, "indexing"),
    (SnapshotSortQueryEngine, "layout"),
    (BucketSummarySmallQueryEngine, "summaries"),
    (BuggyTieBreakEngine, "other"),
    (HotGetCacheQueryEngine, "caching"),
    (BaselineQueryEngine, "other"),
    (DictScanQueryEngine, "layout"),
    (ExclusiveHiBugEngine, "indexing"),
    (PrefixRebuildQueryEngine, "summaries"),
    (StaleRangeCacheBugEngine, "caching"),
    (TopKCacheQueryEngine, "caching"),
    (SnapshotSortQueryEngine, "layout"),
    (BucketSummaryWideQueryEngine, "summaries"),
    (MissingDeleteBugEngine, "indexing"),
    (LazySortedQueryEngine, "indexing"),
    (BaselineQueryEngine, "other"),
    (BuggyTieBreakEngine, "other"),
    (DictScanQueryEngine, "layout"),
    (SumCacheQueryEngine, "caching"),
    (StaleRangeCacheBugEngine, "caching"),
    (FenwickRangeQueryEngine, "summaries"),
    (PrefixRebuildQueryEngine, "summaries"),
    (RangeCacheQueryEngine, "caching"),
    (ExclusiveHiBugEngine, "indexing"),
    (OptimizedQueryEngine, "indexing"),
    (TopKCacheQueryEngine, "caching"),
]

for offset, (factory, mode) in enumerate(_EXTRA_HARD_BRANCH_FACTORIES, start=28):
    branch_name = f"branch_{offset:02d}"
    CANDIDATE_REGISTRY[branch_name] = {
        "factory": factory,
        "file": "candidate/variants.py",
        "mode": mode,
        "description": f"masked hard-search branch {offset:02d}",
    }
