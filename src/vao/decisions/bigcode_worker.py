"""Isolated BigCodeBench checks; full-suite diagnostics never become feedback."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import random
import resource
import sys
import types
import unittest


def check(payload: dict) -> dict:
    spec = importlib.util.spec_from_file_location("public_checks", Path(__file__).with_name("verifier_worker.py"))
    public = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(public)
    random.seed(payload.get("seed", 20261026))
    if payload["mode"] == "visible":
        # Public examples only. The parent strips tests and reference code.
        return public.check(payload)
    if payload["mode"] != "heldout":
        raise ValueError("Unknown BigCodeBench verifier mode")
    capture = public.LimitedOutput()
    # Give unittest.mock the same module identity as the combined submission.
    module = types.ModuleType("__main__")
    sys.modules["__main__"] = module
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            exec(compile(payload["solution"], "candidate.py", "exec", dont_inherit=True), module.__dict__)
            exec(compile(payload["problem"]["test"], "tests.py", "exec", dont_inherit=True), module.__dict__)
            case = module.__dict__["TestCases"]
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
            result = unittest.TextTestRunner(stream=capture, verbosity=0).run(suite)
        return {"passed": result.testsRun > 0 and result.wasSuccessful(), "status": "checked",
                "attempted": result.testsRun, "failed": len(result.failures) + len(result.errors)}
    except BaseException as exc:
        # No private input, assertion text, or traceback leaves this channel.
        return {"passed": False, "status": "candidate_or_suite_error", "error_type": type(exc).__name__}


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_048_576, 1_048_576))
    payload = json.load(sys.stdin)
    result = check(payload)
    sys.__stdout__.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
