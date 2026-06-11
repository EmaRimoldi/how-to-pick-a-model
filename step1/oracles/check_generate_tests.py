"""Inference oracle for generated candidate-only tests."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, ok, public_examples
from runners.sandbox import run_generated_tests


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    tests = state.get("test_suite", {}).get("tests", state.get("tests", []))
    completion = state.get("candidate_completion", state.get("completion", ""))
    if not isinstance(tests, list) or not tests:
        return fail("empty_generated_test_suite")
    public_count = len(public_examples(instance["prompt"], instance["entry_point"]))
    mentions_entry = [test for test in tests if instance["entry_point"] in test]
    if not mentions_entry:
        return fail("tests_do_not_call_entry_point")
    result = run_generated_tests(instance, completion, tests)
    return ok(generated_tests=len(tests), public_examples=public_count, sandbox=result.payload) if result.passed else fail(
        "generated_tests_failed_on_candidate", generated_tests=len(tests), sandbox=result.payload
    )

