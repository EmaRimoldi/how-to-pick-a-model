"""Optimized candidate engine using ordered keys and narrow range slicing."""

from __future__ import annotations

import bisect
import heapq


class OptimizedQueryEngine:
    """Dictionary plus sorted-key index.

    This candidate is still simple, but it exercises a distinct optimization
    mode from the baseline: ordered indexing. It deliberately avoids rebuilding
    full prefix summaries after updates because this benchmark includes bursty
    writes where rebuild spikes hurt p95 latency.
    """

    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {}
        self._keys: list[int] = []
        if items:
            self._values = {int(key): int(value) for key, value in items.items()}
            self._keys = sorted(self._values)

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        if key not in self._values:
            bisect.insort(self._keys, key)
        self._values[key] = value
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        if key not in self._values:
            return None
        del self._values[key]
        index = bisect.bisect_left(self._keys, key)
        if index < len(self._keys) and self._keys[index] == key:
            self._keys.pop(index)
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
        k = int(k)
        left, right = self._range_bounds(lo, hi)
        if left >= right or k <= 0:
            return []
        rows = ((key, self._values[key]) for key in self._keys[left:right])
        return heapq.nsmallest(k, rows, key=lambda item: (-item[1], item[0]))

    def snapshot(self) -> dict[int, int]:
        return dict(self._values)

    def _range_bounds(self, lo: int, hi: int) -> tuple[int, int]:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0, 0
        left = bisect.bisect_left(self._keys, lo)
        right = bisect.bisect_right(self._keys, hi)
        return left, right

