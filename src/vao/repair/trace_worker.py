"""Bounded execution observations, with no expected values or reference program.

Copied as a standalone worker into the same OS sandbox as ordinary verification.
Only exact built-in values are inspected: never call candidate repr/str methods.
The trace is diagnostic candidate data, not a trusted correctness certificate.
"""

from __future__ import annotations

from collections import deque
import contextlib
import importlib
import itertools
import json
import math
import os
import resource
import sys


def compact(value, depth=0):
    """Bound size and recursion without executing arbitrary object protocols."""
    kind = type(value)
    if value is None or kind is bool:
        return value
    if kind is int:
        return value if value.bit_length() <= 256 else {"omitted": "large_integer"}
    if kind is float:
        return value if math.isfinite(value) else {"omitted": "nonfinite_float"}
    if kind is str:
        return value if len(value) <= 96 else {"prefix": value[:96], "length": len(value)}
    if depth < 2 and kind in (list, tuple):
        return {"items": [compact(v, depth + 1) for v in value[:6]], "length": len(value)}
    if depth < 2 and kind is dict:
        return {"items": [[compact(k, depth + 1), compact(v, depth + 1)]
                          for k, v in itertools.islice(value.items(), 6)], "length": len(value)}
    return {"omitted": "object_or_depth_limit"}


class Trace:
    def __init__(self, files):
        self.files = {os.path.abspath(name): name for name in files}
        self.events = deque()
        self.bytes = self.seen = self.dropped = 0
        self.capture_limit_reached = False

    def __call__(self, frame, event, arg):
        filename = self.files.get(frame.f_code.co_filename)
        if filename is None:
            return None
        if event not in {"line", "return", "exception"}:
            return self
        self.seen += 1
        if self.seen > 512:
            self.capture_limit_reached = True
            return None
        row = {"file": filename, "function": frame.f_code.co_name[:96],
               "line": frame.f_lineno, "event": event,
               "locals": {k: compact(v) for k, v in itertools.islice(frame.f_locals.items(), 8)}}
        if event == "return":
            row["returned"] = compact(arg)
        elif event == "exception":
            row["exception"] = type(arg[1]).__name__[:96]
        size = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode())
        if size > 12000:
            row["locals"] = {"omitted": "event_byte_limit"}
            size = len(json.dumps(row, ensure_ascii=True, allow_nan=False).encode())
        self.events.append((row, size))
        self.bytes += size
        while len(self.events) > 32 or self.bytes > 12000:
            _, removed = self.events.popleft()
            self.bytes -= removed
            self.dropped += 1
        return self

    def export(self, intact):
        return {"events": [row for row, _ in self.events], "events_seen": self.seen,
                "events_dropped": self.dropped, "capture_limit_reached": self.capture_limit_reached,
                "intact": intact, "line_semantics": "locals before executing the reported line",
                "limits": {"events": 32, "event_bytes": 12000, "captured_events": 512,
                           "locals_per_event": 8, "value_depth": 2, "container_items": 6, "string_chars": 96}}


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    payload = json.load(sys.stdin)
    sys.path.insert(0, os.getcwd())
    tracer = Trace(payload["trace_files"])
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            module = importlib.import_module(payload["entrypoint"]["module"])
            function = getattr(module, payload["entrypoint"]["function"])
        except BaseException as exc:
            observed = {"status": "load_error", "exception": type(exc).__name__}
            intact = True
        else:
            sys.settrace(tracer)
            try:
                value = function(*payload["args"], **payload["kwargs"])
            except BaseException as exc:
                observed = {"status": "exception", "exception": type(exc).__name__}
            else:
                observed = {"status": "returned", "value": value}
            finally:
                intact = sys.gettrace() is tracer
                sys.settrace(None)
            try:
                encoded = json.dumps(observed, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                observed = {"status": "non_json_output"}
            else:
                if len(encoded.encode()) > 65536:
                    observed = {"status": "output_limit"}
        result = json.dumps({"observed": observed, "trace": tracer.export(intact)}, allow_nan=False)
    sys.__stdout__.write(result + "\n")


if __name__ == "__main__":
    main()
