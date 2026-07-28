"""Inference oracle for the repair node."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, ok
from runners.sandbox import run_generated_tests, run_public_examples


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    completion = state.get("candidate_completion", state.get("completion", ""))
    tests = state.get("test_suite", {}).get("tests", state.get("tests", []))
    public = run_public_examples(instance, completion)
    if not public.passed:
        return fail("repaired_completion_fails_public_examples", public=public.payload)
    if tests:
        generated = run_generated_tests(instance, completion, tests)
        if not generated.passed:
            return fail("repaired_completion_fails_generated_tests", public=public.payload, generated=generated.payload)
        return ok(public=public.payload, generated=generated.payload)
    return ok(public=public.payload, generated=None)

