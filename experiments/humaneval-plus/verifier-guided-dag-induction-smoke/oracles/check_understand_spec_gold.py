"""Offline diagnostic oracle for understand_spec.

This checker may receive canonical_solution in diagnostics, but it only uses it
to confirm the gold completion is executable with the prompt. It is never used
by live solving.
"""

from __future__ import annotations

from typing import Any

from oracles.check_understand_spec import check as check_inference
from runners.sandbox import run_public_examples


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    result = check_inference(instance, state)
    if not result["passed"]:
        return result
    if "canonical_solution" not in instance:
        return {"passed": False, "reason": "missing_canonical_solution_for_diagnostic"}
    public = run_public_examples(instance, instance["canonical_solution"])
    return {"passed": public.passed, "inference": result, "gold_public_examples": public.payload}

