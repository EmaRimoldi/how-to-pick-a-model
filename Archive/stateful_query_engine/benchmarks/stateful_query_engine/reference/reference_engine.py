"""Trusted slow reference engine for semantic verification."""

from __future__ import annotations


class ReferenceQueryEngine:
    """Clear dictionary-backed reference with deterministic sorted scans."""

    def __init__(self, items: dict[int, int] | None = None):
        self._values: dict[int, int] = {}
        if items:
            self._values.update({int(key): int(value) for key, value in items.items()})

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

    def snapshot(self) -> dict[int, int]:
        return dict(self._values)

