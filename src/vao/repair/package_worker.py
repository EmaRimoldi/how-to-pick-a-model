"""Isolated package call; optional bounded coverage includes immutable support."""
from __future__ import annotations

import contextlib
import importlib
import json
import os
import resource
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    payload = json.load(sys.stdin)
    sys.path.insert(0, os.getcwd())
    # Parent writes this fixed helper; the sandbox denies all source mutations.
    from __repair_coverage import Coverage
    tracer = Coverage(payload['coverage_files'])
    covered = sys.argv[1] == 'coverage'
    intact = False
    with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            module = importlib.import_module(payload['entrypoint']['module'])
            function = getattr(module, payload['entrypoint']['function'])
        except BaseException as exc:
            observed = {'status': 'load_error', 'exception': type(exc).__name__}
        else:
            if covered:
                sys.settrace(tracer)
            try:
                value = function(*payload['args'], **payload['kwargs'])
            except BaseException as exc:
                observed = {'status': 'exception', 'exception': type(exc).__name__}
            else:
                observed = {'status': 'returned', 'value': value}
            finally:
                intact = covered and sys.gettrace() is tracer
                sys.settrace(None)
            try:
                encoded = json.dumps(observed, allow_nan=False)
            except (TypeError, ValueError, RecursionError):
                observed = {'status': 'non_json_output'}
            else:
                if len(encoded.encode()) > 65536:
                    observed = {'status': 'output_limit'}
        result = {'observed': observed, 'coverage': tracer.export(intact)} if covered else observed
        result = json.dumps(result, allow_nan=False)
    sys.__stdout__.write(result + '\n')


if __name__ == '__main__':
    main()
