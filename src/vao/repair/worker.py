"""Execute one JSON function call; expected answers stay in the parent process."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import resource
import sys


def main() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    payload = json.load(sys.stdin)
    sys.path.insert(0, os.getcwd())
    with open(os.devnull, "w") as sink:
        result = None
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                module = importlib.import_module(payload["entrypoint"]["module"])
                function = getattr(module, payload["entrypoint"]["function"])
        except BaseException as exc:
            result = json.dumps({"status": "load_error", "exception": type(exc).__name__})
        if result is None:
            try:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    value = function(*payload["args"], **payload["kwargs"])
            except BaseException as exc:
                # Only exceptions raised by the call can satisfy a raises contract.
                result = json.dumps({"status": "exception", "exception": type(exc).__name__})
            else:
                try:
                    result = json.dumps({"status": "returned", "value": value}, allow_nan=False)
                except (TypeError, ValueError, RecursionError):
                    result = json.dumps({"status": "non_json_output"})
        if len(result.encode()) > 65536:
            result = json.dumps({"status": "output_limit"})
    sys.__stdout__.write(result + "\n")


if __name__ == "__main__":
    main()
