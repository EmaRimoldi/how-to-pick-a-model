"""Standalone bounded line coverage during a candidate call, without test labels.

This worker does not reuse sampled trace events: dropped events cannot establish
coverage. Candidate imports precede measurement, as in the existing trace worker.
Only single-threaded entrypoint execution is supported by this diagnostic.
"""
from __future__ import annotations

import contextlib
import importlib
import json
import os
import re
import resource
import sys

VERSION = "entrypoint-line-coverage-v1"
EVENT_LIMIT = 100000
LINE_LIMIT = 4096


class Coverage:
    def __init__(self, files):
        self.files = {os.path.abspath(name): name for name in files}
        self.lines = set()
        self.events = 0
        self.limited = False

    def __call__(self, frame, event, arg):
        filename = self.files.get(frame.f_code.co_filename)
        if filename is None:
            return None
        if event == "line":
            self.events = min(self.events + 1, EVENT_LIMIT + 1)
            if self.events > EVENT_LIMIT:
                self.limited = True
                return None
            location = (filename, frame.f_lineno)
            if location not in self.lines and len(self.lines) >= LINE_LIMIT:
                self.limited = True
                return None
            self.lines.add(location)
        return self

    def export(self, intact):
        return {"version": VERSION, "lines": [list(x) for x in sorted(self.lines)],
                "line_events": self.events, "limit_reached": self.limited,
                "intact": intact, "event_limit": EVENT_LIMIT, "line_limit": LINE_LIMIT}


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    payload = json.load(sys.stdin)
    files = sorted(n for n in os.listdir(".") if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*\.py", n))
    if not 1 <= len(files) <= 2:
        raise ValueError("Invalid isolated candidate inventory")
    tracer = Coverage(files)
    sys.path.insert(0, os.getcwd())
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            module = importlib.import_module(payload["entrypoint"]["module"])
            function = getattr(module, payload["entrypoint"]["function"])
        except BaseException as exc:
            observed = {"status": "load_error", "exception": type(exc).__name__}
            intact = False
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
        result = json.dumps({"observed": observed, "coverage": tracer.export(intact)}, allow_nan=False)
    sys.__stdout__.write(result + "\n")


if __name__ == "__main__":
    main()
