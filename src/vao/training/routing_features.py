"""Feature rendering for routing-only student models."""

from __future__ import annotations

import json
from typing import Any

from vao.agents.base import AgentState
from vao.taxonomy import MODES


DEFAULT_MAX_SOURCE_CHARS = 12000


def record_to_text(record: dict[str, Any], *, max_source_chars: int = DEFAULT_MAX_SOURCE_CHARS) -> str:
    payload = record.get("input", {})
    return _render_payload(payload, max_source_chars=max_source_chars)


def state_to_text(state: AgentState, *, max_source_chars: int = DEFAULT_MAX_SOURCE_CHARS) -> str:
    payload = {
        "profile_summary": state.profile_summary,
        "current_solution_source": state.current_solution_source,
        "current_solution_hash": "",
        "visible_history": state.visible_history,
        "recent_decision_history": [
            {
                "step": item.get("step"),
                "selected_mode": item.get("selected_mode"),
                "mode_probs": item.get("mode_probs"),
            }
            for item in state.visible_history[-5:]
            if isinstance(item, dict)
        ],
        "full_history_summary": f"{len(state.visible_history)} visible steps",
    }
    return _render_payload(payload, max_source_chars=max_source_chars)


def _render_payload(payload: dict[str, Any], *, max_source_chars: int) -> str:
    source = str(payload.get("current_solution_source", ""))
    if len(source) > max_source_chars:
        source = source[:max_source_chars] + "\n# SOURCE_TRUNCATED"
    parts = [
        "PROFILE_SPLIT " + str(payload.get("profile_split", "")),
        "PROFILE " + _compact_json(payload.get("profile_summary", {})),
        "SOLUTION_HASH " + str(payload.get("current_solution_hash", "")),
        "VISIBLE_HISTORY " + _compact_json(payload.get("visible_history", [])),
        "RECENT_DECISIONS " + _compact_json(payload.get("recent_decision_history", [])),
        "FULL_HISTORY " + str(payload.get("full_history_summary", "")),
        "SOURCE\n" + source,
    ]
    return "\n\n".join(parts)


def _compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def structured_features_from_record(record: dict[str, Any]) -> dict[str, float | str]:
    payload = record.get("input") or {}
    profile = payload.get("profile_summary") or {}
    source = str(payload.get("current_solution_source", ""))
    visible_history = payload.get("visible_history") or []
    features: dict[str, float | str] = {
        "profile_id": str(record.get("profile_id", profile.get("profile_id", ""))),
        "profile_split": str(record.get("profile_split") or payload.get("profile_split") or ""),
        "step": float(record.get("step", 0) or 0),
        "source_chars": float(len(source)),
        "source_lines": float(source.count("\n") + 1 if source else 0),
        "visible_history_len": float(len(visible_history)),
        "has_bisect": float("bisect" in source),
        "has_heapq": float("heapq" in source),
        "has_cache": float("cache" in source.lower()),
        "has_fenwick": float("fenwick" in source.lower() or "_bit" in source.lower()),
        "has_slots": float("__slots__" in source),
        "has_sorted_keys": float("_keys" in source or "sorted" in source),
        "range_sum_count": float(source.count("range_sum")),
        "top_k_count": float(source.count("top_k")),
    }
    for mode in MODES:
        features[f"history_selected_{mode}"] = float(
            sum(1 for item in visible_history if isinstance(item, dict) and item.get("selected_mode") == mode)
        )
    return features
