"""Mode taxonomy and lightweight edit classifier."""

from __future__ import annotations

import ast
import difflib
import math
from collections.abc import Mapping
from typing import Any

MODES = ["layout", "indexing", "topk", "caching", "summaries", "micro"]
MODE_SET = set(MODES)

MODE_DESCRIPTIONS = {
    "layout": "Primary storage representation changes.",
    "indexing": "Range access path changes using sorted keys or bounds.",
    "topk": "top_k algorithm, heap, sorting, or tie-breaking changes.",
    "caching": "Memoized query results and invalidation.",
    "summaries": "Maintained aggregates such as prefix sums, buckets, or Fenwick trees.",
    "micro": "Local constant-factor rewrites without structural mechanism changes.",
}


def validate_mode(mode: str) -> str:
    if mode not in MODE_SET:
        raise ValueError(f"Unknown mode {mode!r}; expected one of {MODES}")
    return mode


def normalize_mode_probs(probs: Mapping[str, float]) -> dict[str, float]:
    keys = set(probs)
    if keys != MODE_SET:
        missing = sorted(MODE_SET - keys)
        extra = sorted(keys - MODE_SET)
        raise ValueError(f"mode_probs must contain exactly the six modes; missing={missing}, extra={extra}")
    numeric: dict[str, float] = {}
    for mode in MODES:
        value = float(probs[mode])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid probability for {mode}: {probs[mode]!r}")
        numeric[mode] = value
    total = sum(numeric.values())
    if total <= 0:
        raise ValueError("mode_probs must have positive total mass")
    return {mode: numeric[mode] / total for mode in MODES}


def classify_edit_mode(pre_source: str, post_source: str) -> tuple[str, list[str], dict[str, Any]]:
    """Infer primary and secondary edit modes from diff evidence.

    The classifier is intentionally lightweight and deterministic. It uses
    added-line keywords plus coarse function-level changes rather than trying
    to prove semantic intent.
    """
    if pre_source == post_source:
        return "micro", [], {"reason": "no_source_change", "scores": {"micro": 1.0}}

    added, removed = _changed_lines(pre_source, post_source)
    added_text = "\n".join(added).lower()
    changed_functions = _changed_functions(pre_source, post_source)
    scores = {mode: 0.0 for mode in MODES}
    evidence: dict[str, list[str]] = {mode: [] for mode in MODES}

    def add(mode: str, amount: float, item: str) -> None:
        scores[mode] += amount
        evidence[mode].append(item)

    if any(token in added_text for token in ["_cache", "cache", ".clear()"]):
        add("caching", 10.0, "cache keyword or invalidation in added lines")

    if any(token in added_text for token in ["_prefix", "_fenwick", "_bit", "_bucket", "_sum_tree", "_count_tree"]):
        add("summaries", 10.0, "maintained aggregate structure keyword in added lines")

    if any(token in added_text for token in ["bisect_left", "bisect_right", "insort", "_keys", "_range_bounds"]):
        add("indexing", 4.0, "sorted-key or range-bound indexing keyword in added lines")

    if "top_k" in changed_functions:
        add("topk", 3.0, "top_k function body changed")
    if "heapq" in added_text or "nsmallest" in added_text or "nlargest" in added_text:
        add("topk", 3.0, "heap-based top-k evidence in added lines")
    if "lambda item: (-item[1], item[0])" in added_text and "top_k" in changed_functions:
        add("topk", 1.0, "top-k tie-breaking evidence")

    primary_methods = {"__init__", "put", "delete", "get"}
    changed_primary = sorted(primary_methods & changed_functions)
    if changed_primary:
        add("layout", float(len(changed_primary)), f"primary methods changed: {changed_primary}")
    if any(token in added_text for token in ["_values", "dict[", "items.items()", "snapshot"]):
        add("layout", 2.0, "dictionary storage representation evidence")
    if "_items" in "\n".join(removed).lower() and "_values" in added_text:
        add("layout", 3.0, "storage moved from _items toward _values")

    if all(scores[mode] == 0.0 for mode in MODES if mode != "micro"):
        local_rewrite_score = 1.0 + min(len(added) + len(removed), 20) / 20.0
        add("micro", local_rewrite_score, "no structural keyword evidence")

    priority = ["caching", "summaries", "layout", "indexing", "topk", "micro"]
    primary = max(MODES, key=lambda mode: (scores[mode], -priority.index(mode)))
    if scores[primary] <= 0:
        primary = "micro"
    secondary = [
        mode
        for mode in sorted(MODES, key=lambda mode: scores[mode], reverse=True)
        if mode != primary and mode != "micro" and scores[mode] > 0
    ]
    if primary != "micro" and scores["micro"] > 0:
        secondary.append("micro")
    details = {
        "scores": scores,
        "evidence": {mode: rows for mode, rows in evidence.items() if rows},
        "changed_functions": sorted(changed_functions),
        "added_line_count": len(added),
        "removed_line_count": len(removed),
    }
    return primary, secondary, details


def _changed_lines(pre_source: str, post_source: str) -> tuple[list[str], list[str]]:
    added: list[str] = []
    removed: list[str] = []
    for line in difflib.ndiff(pre_source.splitlines(), post_source.splitlines()):
        if line.startswith("+ "):
            added.append(line[2:])
        elif line.startswith("- "):
            removed.append(line[2:])
    return added, removed


def _changed_functions(pre_source: str, post_source: str) -> set[str]:
    pre = _function_sources(pre_source)
    post = _function_sources(post_source)
    names = set(pre) | set(post)
    return {name for name in names if pre.get(name) != post.get(name)}


def _function_sources(source: str) -> dict[str, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    functions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            end = getattr(node, "end_lineno", node.lineno)
            functions[node.name] = "\n".join(lines[node.lineno - 1 : end])
    return functions
