"""Standalone sandbox child: public doctests or official EvalPlus base/plus checks."""

from __future__ import annotations

import contextlib
import ast
import doctest
import io
import json
import os
import resource
import inspect
import re
import socket
import sys
from copy import deepcopy


def public_examples_doc(prompt: str) -> str:
    """Extract the function docstring, excluding source-level closing quotes."""
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body or not isinstance(node.body[0], ast.Expr):
                return ""
            value = node.body[0].value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return ""
            # Preserve source escapes: decoding \n inside an example's string
            # literal would turn valid public examples into malformed doctests.
            source = ast.get_source_segment(prompt, value) or ""
            match = re.fullmatch(r"(?is)[ru]*('''|\"\"\")(.*)\1", source)
            return inspect.cleandoc(match.group(2)) if match else ""
    return ""


class ExampleChecker(doctest.OutputChecker):
    """Accept equivalent Python literals, including single/double quoted strings."""

    def check_output(self, want, got, flags):
        try:
            return ast.literal_eval(want.strip()) == ast.literal_eval(got.strip())
        except (ValueError, SyntaxError):
            return super().check_output(want, got, flags)


class LimitedOutput(io.StringIO):
    """Bound model-controlled print output inside the verifier."""

    def write(self, value):
        if self.tell() + len(value) > 16384:
            raise RuntimeError("Candidate output limit exceeded")
        return super().write(value)


def probe() -> dict:
    """Check the sandbox's actual access controls, not merely its configuration."""
    from evalplus.eval import untrusted_check  # noqa: F401
    result = {"evalplus_available": True, "credential_environment_empty": not any(
        "KEY" in key or "TOKEN" in key for key in os.environ)}
    try:
        open("/etc/passwd").read()
        result["private_files_denied"] = False
    except PermissionError:
        result["private_files_denied"] = True
    try:
        os.listdir("/Users")
        result["home_directories_denied"] = False
    except PermissionError:
        result["home_directories_denied"] = True
    try:
        socket.socket().connect(("1.1.1.1", 443))
        result["network_denied"] = False
    except PermissionError:
        result["network_denied"] = True
    return result


def check(payload: dict) -> dict:
    """Score without exposing the hidden evaluator's inputs or reference solution."""
    problem, solution = payload["problem"], payload["solution"]
    if payload["mode"] == "probe":
        return probe()
    if payload["mode"] == "visible":
        capture = LimitedOutput()
        try:
            namespace = {}
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                # Match EvalPlus compilation: do not inherit this worker's
                # __future__.annotations and hide missing typing imports.
                exec(compile(solution, "candidate.py", "exec", dont_inherit=True), namespace)
                test = doctest.DocTestParser().get_doctest(public_examples_doc(problem["prompt"]), namespace,
                    problem["entry_point"], "public_examples", 0)
                for example in test.examples:
                    # Some HumanEval prompts state a predicate without printing
                    # its expected True. Treat that public predicate as a check.
                    if not example.want:
                        statements = ast.parse(example.source).body
                        if statements and isinstance(statements[-1], ast.Expr) and isinstance(
                                statements[-1].value, (ast.Compare, ast.BoolOp)):
                            example.want = "True\n"
                runner = doctest.DocTestRunner(checker=ExampleChecker(), optionflags=doctest.ELLIPSIS)
                result = runner.run(test, out=capture.write)
            return {"passed": result.attempted > 0 and result.failed == 0,
                    "status": "pass" if result.attempted > 0 and result.failed == 0 else "fail",
                    "attempted": result.attempted, "failed": result.failed,
                    "feedback": capture.getvalue()[-6000:]}
        except BaseException as exc:
            return {"passed": False, "status": "error",
                    "feedback": f"{type(exc).__name__}: {str(exc)[:1000]}"}
    from evalplus.eval import untrusted_check
    from evalplus.gen.util import trusted_exec
    reference = problem["prompt"] + problem["canonical_solution"]
    if payload["mode"] == "base_feedback":
        # This protocol explicitly publishes base cases; Plus cases are absent
        # from this subprocess payload and remain evaluation-only.
        capture = LimitedOutput()
        try:
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                exec(compile(solution, "candidate.py", "exec", dont_inherit=True), {})
        except BaseException as exc:
            return {"passed": False, "status": "error", "attempted": len(problem["base_input"]),
                    "failed": len(problem["base_input"]), "feedback": f"{type(exc).__name__}: {str(exc)[:500]}"}
        inputs = problem["base_input"]
        expected, timings = trusted_exec(reference, deepcopy(inputs), problem["entry_point"], record_time=True)
        status, details = untrusted_check("humaneval", solution, deepcopy(inputs), problem["entry_point"],
            expected, problem["atol"], timings, fast_check=False)
        failing = [i for i in range(len(inputs)) if i >= len(details) or not details[i]]
        examples = [{"arguments": repr(inputs[i])[:250], "acceptable_reference_output": repr(expected[i])[:250]}
                    for i in failing[:3]]
        return {"passed": status == "pass", "status": status, "attempted": len(inputs),
                "failed": len(failing), "feedback": json.dumps({"public_base_status": status,
                    "failing_examples": examples, "note": "Reference outputs are examples; task-specific tolerance or valid-output rules still apply."})}
    results = {}
    for suite in ("base", "plus"):
        inputs = problem[suite + "_input"]
        expected, timings = trusted_exec(reference, deepcopy(inputs), problem["entry_point"], record_time=True)
        status, _ = untrusted_check("humaneval", solution, deepcopy(inputs),
            problem["entry_point"], expected, problem["atol"], timings, fast_check=True)
        results[suite] = status
    return {"passed": all(v == "pass" for v in results.values()), "status": results}


def main() -> None:
    """Apply resource limits before reading candidate code and emit a single result."""
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_048_576, 1_048_576))
    # macOS cannot reliably enforce RLIMIT_AS for Python; the OS sandbox is
    # the security boundary and the parent also enforces a wall-clock timeout.
    try:
        result = check(json.load(sys.stdin))
    except BaseException as exc:
        result = {"infrastructure_error": f"{type(exc).__name__}: {str(exc)[:1000]}"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
