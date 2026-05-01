from __future__ import annotations

from vao.agents.local_stub_adapter import CACHING_SOURCE, INDEXING_SOURCE, SUMMARIES_SOURCE
from vao.taxonomy import classify_edit_mode


BASE = '''from __future__ import annotations

class CandidateQueryEngine:
    def __init__(self, items=None):
        self._items = []
    def put(self, key, value):
        self._items.append((key, value))
    def delete(self, key):
        self._items = []
    def get(self, key):
        return None
    def range_sum(self, lo, hi):
        return 0
    def aggregate_count(self, lo, hi):
        return 0
    def top_k(self, lo, hi, k):
        return []
'''


def test_classifier_detects_caching() -> None:
    primary, secondary, details = classify_edit_mode(BASE, CACHING_SOURCE)
    assert primary == "caching"
    assert "cache" in str(details).lower()


def test_classifier_detects_summaries() -> None:
    primary, _, _ = classify_edit_mode(BASE, SUMMARIES_SOURCE)
    assert primary == "summaries"


def test_classifier_compound_layout_indexing() -> None:
    primary, secondary, details = classify_edit_mode(BASE, INDEXING_SOURCE)
    assert primary in {"layout", "indexing"}
    assert {"layout", "indexing"} <= ({primary} | set(secondary))
    assert details["scores"]["layout"] > 0
    assert details["scores"]["indexing"] > 0
