"""Shared action-mode taxonomy for branch generation and verifier logging."""

from __future__ import annotations

from dataclasses import dataclass


MODES = ["layout", "indexing", "topk", "caching", "summaries", "micro"]
MODE_SET = set(MODES)
DEFAULT_MODE = "micro"


MODE_DESCRIPTIONS = {
    "layout": "Representation, architecture, or structural layout changes.",
    "indexing": "Access-path, optimizer, or selection-logic changes.",
    "topk": "Ranking, threshold, or top-k style prioritization changes.",
    "caching": "Memoization, regularization, or reuse-oriented changes.",
    "summaries": "Aggregate, schedule, or summary-statistic changes.",
    "micro": "Small local fixes and low-level tuning changes.",
}


@dataclass(frozen=True)
class ModeSpec:
    key: str
    description: str


MODE_SPECS = {key: ModeSpec(key=key, description=MODE_DESCRIPTIONS[key]) for key in MODES}


def validate_mode(mode: str) -> str:
    if mode not in MODE_SET:
        raise ValueError(f"unknown_mode:{mode!r}")
    return mode
