"""Correct but intentionally inefficient baseline candidate engine."""

from __future__ import annotations


class BaselineQueryEngine:
    """List-backed implementation with linear scans for range operations."""

    def __init__(self, items: dict[int, int] | None = None):
        self._items: list[tuple[int, int]] = []
        if items:
            for key, value in items.items():
                self.put(key, value)

    def put(self, key: int, value: int) -> None:
        key = int(key)
        value = int(value)
        for index, (existing_key, _) in enumerate(self._items):
            if existing_key == key:
                self._items[index] = (key, value)
                return None
        self._items.append((key, value))
        return None

    def delete(self, key: int) -> None:
        key = int(key)
        self._items = [(existing_key, value) for existing_key, value in self._items if existing_key != key]
        return None

    def get(self, key: int) -> int | None:
        key = int(key)
        for existing_key, value in self._items:
            if existing_key == key:
                return value
        return None

    def range_sum(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        total = 0
        for key, value in self._items:
            if lo <= key <= hi:
                total += value
        return total

    def aggregate_count(self, lo: int, hi: int) -> int:
        lo = int(lo)
        hi = int(hi)
        if lo > hi:
            return 0
        count = 0
        for key, _ in self._items:
            if lo <= key <= hi:
                count += 1
        return count

    def top_k(self, lo: int, hi: int, k: int) -> list[tuple[int, int]]:
        lo = int(lo)
        hi = int(hi)
        k = int(k)
        if lo > hi or k <= 0:
            return []
        rows = [(key, value) for key, value in self._items if lo <= key <= hi]
        rows.sort(key=lambda item: (-item[1], item[0]))
        return rows[:k]

    def snapshot(self) -> dict[int, int]:
        return {key: value for key, value in self._items}

