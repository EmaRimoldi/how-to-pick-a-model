"""Shared action-mode taxonomy for branch generation and verifier logging."""

from __future__ import annotations

import math
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


def normalize_mode_probs(mode_probs: dict[str, float]) -> dict[str, float]:
    if not isinstance(mode_probs, dict):
        raise ValueError("mode_probs must be a dict")
    keys = set(mode_probs)
    if keys != MODE_SET:
        missing = sorted(MODE_SET - keys)
        extra = sorted(keys - MODE_SET)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ValueError("mode_probs must contain exactly the canonical modes" + (f" ({', '.join(details)})" if details else ""))

    normalized: dict[str, float] = {}
    total = 0.0
    for mode in MODES:
        try:
            value = float(mode_probs[mode])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"mode_prob_not_numeric:{mode}") from exc
        if not math.isfinite(value):
            raise ValueError(f"mode_prob_not_finite:{mode}")
        if value < 0:
            raise ValueError(f"mode_prob_negative:{mode}")
        normalized[mode] = value
        total += value

    if total <= 0.0:
        raise ValueError("mode_probs must have positive total mass")
    return {mode: normalized[mode] / total for mode in MODES}
