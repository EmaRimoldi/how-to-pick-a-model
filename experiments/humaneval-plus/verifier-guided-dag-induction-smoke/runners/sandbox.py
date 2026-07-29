"""Sandboxed HumanEval execution helpers.

All candidate completions and generated tests are executed in an isolated
Python subprocess with a timeout and restricted environment. This mirrors the
official HumanEval guarded-execution discipline: the parent process never
executes untrusted candidate code in-process.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from typing import Any, Literal


SandboxMode = Literal["terminal", "public", "generated"]


_WORKER = r"""
import builtins
import contextlib
import doctest
import faulthandler
import io
import json
import os
import resource
import signal
import sys
import traceback


def reliability_guard(maximum_memory_bytes=None):
    if maximum_memory_bytes is not None:
        resource.setrlimit(resource.RLIMIT_AS, (maximum_memory_bytes, maximum_memory_bytes))
        resource.setrlimit(resource.RLIMIT_DATA, (maximum_memory_bytes, maximum_memory_bytes))
    faulthandler.disable()
    builtins.exit = None
    builtins.quit = None
    builtins.open = None
    os.environ.clear()
    os.chdir = None
    os.getcwd = None
    os.listdir = None
    os.remove = None
    os.removedirs = None
    os.rmdir = None
    os.system = None
    os.putenv = None
    os.kill = None
    os.fork = None
    os.forkpty = None
    os.rename = None
    os.renames = None
    os.truncate = None
    os.replace = None


def timeout_handler(signum, frame):
    raise TimeoutError("sandbox alarm expired")


def run_payload(payload):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(payload.get("timeout_seconds", 3)))
    reliability_guard(payload.get("maximum_memory_bytes", 256 * 1024 * 1024))
    namespace = {}
    program = payload["prompt"] + payload["completion"]
    exec(program, namespace)
    entry_point = payload["entry_point"]
    mode = payload["mode"]
    if entry_point not in namespace:
        raise NameError(f"entry point {entry_point!r} was not defined")
    if mode == "public":
        doc = namespace[entry_point].__doc__ or ""
        examples = doctest.DocTestParser().get_examples(doc)
        checker = doctest.OutputChecker()
        failures = []
        for index, example in enumerate(examples):
            output = io.StringIO()
            try:
                try:
                    code = compile(example.source, f"<doctest {entry_point}>", "eval")
                    with contextlib.redirect_stdout(output):
                        value = eval(code, namespace)
                    got = output.getvalue()
                    if value is not None:
                        got += repr(value) + "\n"
                except SyntaxError:
                    code = compile(example.source, f"<doctest {entry_point}>", "exec")
                    with contextlib.redirect_stdout(output):
                        exec(code, namespace)
                    got = output.getvalue()
            except BaseException as exc:
                failures.append({"index": index, "error": type(exc).__name__, "message": str(exc)})
                continue
            flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
            if not checker.check_output(example.want, got, flags):
                failures.append({"index": index, "expected": example.want, "got": got})
        if failures:
            return {"passed": False, "mode": mode, "failures": failures}
        return {"passed": True, "mode": mode, "failures": []}
    if mode == "generated":
        failures = []
        for index, test_code in enumerate(payload.get("generated_tests", [])):
            try:
                exec(test_code, namespace)
            except BaseException as exc:
                failures.append({"index": index, "error": type(exc).__name__, "message": str(exc)})
        if failures:
            return {"passed": False, "mode": mode, "failures": failures}
        return {"passed": True, "mode": mode, "failures": []}
    if mode == "terminal":
        exec(payload["test"], namespace)
        namespace["check"](namespace[entry_point])
        return {"passed": True, "mode": mode, "failures": []}
    raise ValueError(f"unknown sandbox mode: {mode}")


try:
    payload = json.load(sys.stdin)
    result = run_payload(payload)
except BaseException as exc:
    result = {
        "passed": False,
        "mode": locals().get("payload", {}).get("mode"),
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(limit=8),
    }
print(json.dumps(result, sort_keys=True))
"""


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    mode: SandboxMode
    wall_ms: int
    payload: dict[str, Any]
    timeout: bool = False


def run_candidate(
    *,
    prompt: str,
    completion: str,
    entry_point: str,
    mode: SandboxMode,
    test: str | None = None,
    generated_tests: list[str] | None = None,
    timeout_seconds: int = 3,
) -> SandboxResult:
    request = {
        "prompt": prompt,
        "completion": completion,
        "entry_point": entry_point,
        "mode": mode,
        "test": test or "",
        "generated_tests": generated_tests or [],
        "timeout_seconds": timeout_seconds,
    }
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONHASHSEED": "0",
    }
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _WORKER],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=timeout_seconds + 1,
            env=env,
            cwd="/tmp",
            check=False,
        )
    except subprocess.TimeoutExpired:
        wall_ms = int((time.perf_counter() - started) * 1000)
        return SandboxResult(
            passed=False,
            mode=mode,
            wall_ms=wall_ms,
            payload={"passed": False, "mode": mode, "error_type": "TimeoutExpired", "error": "subprocess timeout"},
            timeout=True,
        )
    wall_ms = int((time.perf_counter() - started) * 1000)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        payload = {
            "passed": False,
            "mode": mode,
            "error_type": "SandboxProtocolError",
            "error": proc.stderr.strip() or proc.stdout.strip(),
            "returncode": proc.returncode,
        }
    return SandboxResult(passed=bool(payload.get("passed")), mode=mode, wall_ms=wall_ms, payload=payload)


def run_public_examples(instance: dict[str, Any], completion: str, *, timeout_seconds: int = 3) -> SandboxResult:
    return run_candidate(
        prompt=instance["prompt"],
        completion=completion,
        entry_point=instance["entry_point"],
        mode="public",
        timeout_seconds=timeout_seconds,
    )


def run_generated_tests(
    instance: dict[str, Any],
    completion: str,
    generated_tests: list[str],
    *,
    timeout_seconds: int = 3,
) -> SandboxResult:
    return run_candidate(
        prompt=instance["prompt"],
        completion=completion,
        entry_point=instance["entry_point"],
        mode="generated",
        generated_tests=generated_tests,
        timeout_seconds=timeout_seconds,
    )


def run_terminal_verifier(instance: dict[str, Any], completion: str, *, timeout_seconds: int = 3) -> SandboxResult:
    if "test" not in instance:
        raise KeyError("terminal verifier requires instance['test']")
    return run_candidate(
        prompt=instance["prompt"],
        completion=completion,
        entry_point=instance["entry_point"],
        mode="terminal",
        test=instance["test"],
        timeout_seconds=timeout_seconds,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run one sandboxed HumanEval candidate payload.")
    parser.add_argument("--payload-json", required=True, help="JSON object with prompt, completion, entry_point, mode.")
    args = parser.parse_args(argv)
    payload = json.loads(args.payload_json)
    result = run_candidate(
        prompt=payload["prompt"],
        completion=payload["completion"],
        entry_point=payload["entry_point"],
        mode=payload["mode"],
        test=payload.get("test"),
        generated_tests=payload.get("generated_tests"),
        timeout_seconds=int(payload.get("timeout_seconds", 3)),
    )
    print(json.dumps({"passed": result.passed, "wall_ms": result.wall_ms, **result.payload}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
