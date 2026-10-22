"""Run public doctest feedback and private EvalPlus scoring in an OS sandbox."""

from __future__ import annotations

import doctest
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .verifier_worker import public_examples_doc


def visible_examples(prompt: str) -> int:
    """Count only examples already included in the public task prompt."""
    try:
        return len(doctest.DocTestParser().get_examples(public_examples_doc(prompt)))
    except ValueError:
        return 0  # Public documentation cannot be executed unambiguously.


def sandbox_profile(work: Path) -> str:
    """Allow interpreter/library reads and temporary writes, with no network/home access."""
    read_roots = {"/System", "/usr", "/bin", "/dev", "/private/var/db",
                  str(Path(sys.base_prefix).resolve()), str(Path(sys.prefix).resolve()),
                  str(Path(__file__).resolve().parent), str(work.resolve())}
    reads = " ".join("(subpath " + json.dumps(p) + ")" for p in sorted(read_roots))
    return ("(version 1)(deny default)(allow process-exec process-fork sysctl-read)"
            "(allow file-read*)"
            "(deny file-read* (subpath \"/Users\") (subpath \"/private/tmp\")"
            " (subpath \"/private/var/folders\") (subpath \"/private/var/tmp\")"
            " (subpath \"/Volumes\") (literal \"/private/etc/passwd\"))"
            f"(allow file-read* {reads})"
            f"(allow file-write* (subpath {json.dumps(str(work.resolve()))}) (literal \"/dev/null\"))"
            "(allow ipc-posix-shm ipc-posix-sem)")


class SandboxVerifier:
    """Fail closed on hosts without the supported macOS sandbox.

    CPU limits alone are not an isolation boundary. A Linux/container backend
    can implement the same interface later; this pilot does not silently fall
    back to executing generated code in an unrestricted host process.
    """

    def __init__(self, timeout: int = 30):
        if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
            raise RuntimeError("Live verification currently requires macOS sandbox-exec")
        self.timeout = timeout

    def check(self, problem: dict, solution: str, mode: str) -> dict:
        """Keep hidden tests out of the visible-feedback channel."""
        if mode not in {"visible", "heldout", "probe", "base_feedback"}:
            raise ValueError("Unknown verifier mode")
        if mode == "visible":
            problem = {"prompt": problem["prompt"], "entry_point": problem["entry_point"]}
        elif mode == "base_feedback":
            problem = {k: problem[k] for k in ("prompt", "entry_point", "canonical_solution", "base_input", "atol")}
        with tempfile.TemporaryDirectory(prefix="decision-verifier-") as temp:
            work = Path(temp)
            env = {"PATH": "/usr/bin:/bin", "HOME": temp, "TMPDIR": temp,
                   "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                   "VECLIB_MAXIMUM_THREADS": "1", "EVALPLUS_MAX_MEMORY_BYTES": "-1"}
            command = ["sandbox-exec", "-p", sandbox_profile(work), sys.executable, "-I",
                       str(Path(__file__).with_name("verifier_worker.py"))]
            try:
                result = subprocess.run(command, input=json.dumps({"problem": problem,
                    "solution": solution, "mode": mode}), text=True, capture_output=True,
                    timeout=self.timeout, cwd=work, env=env)
            except subprocess.TimeoutExpired:
                return {"passed": False, "status": "timeout", "feedback": "Verification timed out"}
            try:
                payload = json.loads(result.stdout)
            except ValueError:
                raise RuntimeError("Sandbox verifier failed before producing a result: "
                                   + result.stderr[-1000:]) from None
            if payload.get("infrastructure_error"):
                raise RuntimeError("Sandbox verifier infrastructure error: " + payload["infrastructure_error"])
            return payload

    def preflight(self) -> dict:
        """Confirm filesystem/network denial and a working EvalPlus environment."""
        result = self.check({}, "", "probe")
        if not all(result.values()):
            raise RuntimeError("Verifier sandbox isolation probe failed")
        return result
