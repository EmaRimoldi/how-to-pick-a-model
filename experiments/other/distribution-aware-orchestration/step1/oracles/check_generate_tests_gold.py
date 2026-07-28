"""Offline diagnostic oracle for generated tests against the gold completion."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, ok
from runners.sandbox import run_generated_tests


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if "canonical_solution" not in instance:
        return fail("missing_canonical_solution_for_diagnostic")
    tests = state.get("test_suite", {}).get("tests", state.get("tests", []))
    if not tests:
        return fail("empty_generated_test_suite")
    result = run_generated_tests(instance, instance["canonical_solution"], tests)
    return ok(generated_tests=len(tests), gold_sandbox=result.payload) if result.passed else fail(
        "generated_tests_reject_gold", generated_tests=len(tests), gold_sandbox=result.payload
    )

