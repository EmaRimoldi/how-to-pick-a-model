"""Inference oracle for deterministic routing decisions."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, ok


ALLOWED_PATHS = {
    "easy": ["understand_spec", "implement", "run_tests"],
    "medium": ["understand_spec", "plan", "implement", "run_tests", "repair"],
    "hard": ["understand_spec", "plan", "generate_tests", "implement", "run_tests", "repair"],
}


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    decision = state.get("route_decision", state)
    difficulty = decision.get("difficulty")
    path = decision.get("path")
    if difficulty not in ALLOWED_PATHS:
        return fail("unknown_difficulty", difficulty=difficulty)
    if path != ALLOWED_PATHS[difficulty]:
        return fail("path_mismatch", difficulty=difficulty, expected=ALLOWED_PATHS[difficulty], got=path)
    return ok(difficulty=difficulty, path=path)

