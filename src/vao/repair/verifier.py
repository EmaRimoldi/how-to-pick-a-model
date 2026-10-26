"""Verify function-repair artifacts in fresh macOS sandboxes with parent-side scoring."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from vao.decisions.verification import sandbox_profile
from .environment import canonical, validate_cases, validate_files


class RepairVerifier:
    """No unrestricted fallback; each call sees only code and its current input.

    This first backend follows the repository's macOS sandbox requirement.
    Other hosts can prepare requests and audit artifacts, but cannot execute
    candidates until a separately tested OS-isolation backend is implemented.
    """

    def __init__(self, timeout: float = 5):
        if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
            raise RuntimeError("Python repair execution requires macOS sandbox-exec")
        if not 0 < timeout <= 30:
            raise ValueError("Timeout must be between 0 and 30 seconds")
        self.timeout = timeout

    def invoke(self, files: dict, entrypoint: dict, case: dict) -> dict:
        """Run one candidate call with no expectations, suite, credentials or history."""
        result = self._execute(files, entrypoint, case, worker="worker.py")
        return self._observation(result)

    @staticmethod
    def _observation(result: dict) -> dict:
        status = result.get("status")
        if status == "returned" and set(result) == {"status", "value"}:
            return result
        if status in {"exception", "load_error"} and set(result) == {"status", "exception"} and isinstance(result["exception"], str):
            return result
        if result in ({"status": "output_limit"}, {"status": "non_json_output"},
                      {"status": "timeout"}, {"status": "invalid_output"}):
            return result
        if status == "worker_exit" and set(result) == {"status", "returncode"}:
            return result
        return {"status": "invalid_output"}

    def trace(self, files: dict, entrypoint: dict, case: dict) -> dict:
        """Observe a bounded candidate-only trace; it never determines a pass flag."""
        result = self._execute(files, entrypoint, case, worker="trace_worker.py")
        if set(result) != {"observed", "trace"} or not isinstance(result["observed"], dict):
            return {"available": False, "reason": "trace_worker_failure", "worker_result": result}
        trace = result["trace"]
        if (not isinstance(trace, dict) or len(canonical(trace).encode()) > 16384
                or not isinstance(trace.get("events"), list) or len(trace["events"]) > 32
                or type(trace.get("intact")) is not bool):
            return {"available": False, "reason": "invalid_trace"}
        return {"available": trace["intact"], "reason": None if trace["intact"] else "tracing_disabled",
                "observed": self._observation(result["observed"]), "trace": trace}

    def _execute(self, files: dict, entrypoint: dict, case: dict, *, worker: str) -> dict:
        """Shared OS boundary; payload allowlists inputs and omits expected answers."""
        validate_files(files)
        with tempfile.TemporaryDirectory(prefix="repair-verifier-") as temp:
            work = Path(temp)
            for name, source in files.items():
                (work / name).write_text(source, encoding="utf-8")
            runner = work / "__repair_worker.py"
            shutil.copyfile(Path(__file__).with_name(worker), runner)
            payload = {"entrypoint": entrypoint, "args": case["args"], "kwargs": case.get("kwargs", {})}
            if worker == "trace_worker.py":
                payload["trace_files"] = sorted(files)
            env = {"PATH": "/usr/bin:/bin", "HOME": temp, "TMPDIR": temp,
                   "PYTHONHASHSEED": "0", "TZ": "UTC", "LANG": "C"}
            command = ["sandbox-exec", "-p", sandbox_profile(work), sys.executable, "-I", str(runner)]
            # Regular output files obey the child's FSIZE bound, unlike PIPE buffers.
            with (work / "stdout").open("w+b") as out, (work / "stderr").open("w+b") as err:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                           cwd=work, env=env, start_new_session=True)
                timed_out = False
                try:
                    process.communicate(canonical(payload).encode(), timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    # Also remove spawned descendants when the direct child has exited.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                if timed_out:
                    return {"status": "timeout"}
                out.seek(0)
                raw = out.read(131073)
                if process.returncode != 0:
                    return {"status": "worker_exit", "returncode": process.returncode}
                try:
                    result = json.loads(raw)
                    canonical(result)
                except (ValueError, UnicodeError, RecursionError):
                    return {"status": "invalid_output"}
                if not isinstance(result, dict):
                    return {"status": "invalid_output"}
                return result

    def check(self, files: dict, entrypoint: dict, cases: list) -> dict:
        """Judge expected values in the parent, never a candidate-reported pass flag."""
        validate_cases(cases)
        start = time.monotonic()
        outcomes = []
        for case in cases:
            actual = self.invoke(files, entrypoint, case)
            if "expected" in case:
                passed = actual.get("status") == "returned" and canonical(actual.get("value")) == canonical(case["expected"])
            else:
                passed = actual == {"status": "exception", "exception": case["raises"]}
            outcomes.append({"id": case["id"], "passed": passed, "observed": actual})
        passed_cases = sum(row["passed"] for row in outcomes)
        return {"passed": passed_cases == len(cases), "passed_cases": passed_cases,
                "total_cases": len(cases), "cases": outcomes,
                "verifier_seconds": time.monotonic() - start}

    def preflight(self) -> dict:
        """Probe the actual sandbox before accepting any verifier result."""
        with tempfile.TemporaryDirectory(prefix="repair-private-probe-") as temp:
            sentinel = Path(temp) / "private.txt"
            sentinel.write_text("evaluator-only-sentinel")
            code = """import os, socket
def probe(path):
    denied_file = denied_network = False
    try:
        open(path).read()
    except PermissionError:
        denied_file = True
    try:
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        s.close()
    except PermissionError:
        denied_network = True
    return [denied_file, denied_network, not any('KEY' in k or 'TOKEN' in k for k in os.environ)]
"""
            result = self.invoke({"probe.py": code}, {"module": "probe", "function": "probe"},
                                 {"args": [str(sentinel)]})
        if result != {"status": "returned", "value": [True, True, True]}:
            raise RuntimeError("Repair sandbox preflight failed: " + canonical(result))
        return {"filesystem_denied": True, "network_denied": True, "credentials_absent": True,
                "backend": "macos-sandbox-exec", "python": sys.version.split()[0]}
