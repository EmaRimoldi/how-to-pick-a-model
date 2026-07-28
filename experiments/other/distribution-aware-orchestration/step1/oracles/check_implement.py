"""Inference oracle for the implement node."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, ok
from runners.sandbox import run_public_examples


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    completion = state.get("candidate_completion", state.get("completion", ""))
    if not isinstance(completion, str) or not completion.strip():
        return fail("empty_completion")
    result = run_public_examples(instance, completion)
    return ok(sandbox=result.payload) if result.passed else fail("public_examples_failed", sandbox=result.payload)

