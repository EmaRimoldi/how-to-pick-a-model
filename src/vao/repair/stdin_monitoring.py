"""Opt-in CPython monitoring backend; the frozen legacy stdin executor stays intact.

The native execution boundary is deliberately retained verbatim for the new
coverage worker; ordinary execution delegates to the original backend.
"""
from __future__ import annotations
import base64
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
from .stdin_verifier import StdinVerifier, valid_stdin_coverage


def valid_monitoring_coverage(data, source):
    return (isinstance(data, dict) and data.get('version') == 'stdin-monitoring-line-coverage-v1'
            and valid_stdin_coverage({**data, 'version': 'stdin-main-line-coverage-v1'}, source))


class MonitoringStdinVerifier(StdinVerifier):
    def __init__(self, timeout=5):
        super().__init__(timeout)
        if not hasattr(sys, 'monitoring'):
            raise RuntimeError('Monitoring coverage requires CPython 3.12 or later')

    def invoke(self, source: bytes, stdin: bytes, *, coverage: bool = False) -> dict:
        if not coverage:
            return super().invoke(source, stdin)
        if not isinstance(source, bytes) or not 0 < len(source) <= 262144:
            raise ValueError('Program must contain 1..262144 source bytes')
        if not isinstance(stdin, bytes) or len(stdin) > 65536:
            raise ValueError('stdin must contain at most 65536 bytes')
        if type(coverage) is not bool:
            raise ValueError('Coverage mode must be boolean')
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='repair-stdin-') as temp:
            work = Path(temp).resolve()
            code, scratch = work / 'source', work / 'scratch'
            code.mkdir(); scratch.mkdir()
            (code / 'main.py').write_bytes(source)
            for original, local in [('stdin_monitoring_worker.py', '__repair_worker.py'),
                                    ('monitoring_coverage.py', '__repair_monitor.py')]:
                shutil.copyfile(Path(__file__).with_name(original), code / local)
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(scratch), 'TMPDIR': str(scratch),
                   'PYTHONHASHSEED': '0', 'TZ': 'UTC', 'LANG': 'C', 'PYTHONIOENCODING': 'utf-8'}
            profile = sandbox_profile(work) + f'(deny file-write* (subpath {json.dumps(str(code))}))'
            command = ['sandbox-exec', '-p', profile, sys.executable, '-I',
                       str(code / '__repair_worker.py'), 'coverage' if coverage else 'ordinary']
            with (work / 'stdout').open('w+b') as out, (work / 'stderr').open('w+b') as err:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                           cwd=code, env=env, start_new_session=True)
                timed_out = False
                try:
                    process.communicate(stdin, timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                out.seek(0); err.seek(0)
                raw_out, raw_err = out.read(131073), err.read(131073)
                status = 'timeout' if timed_out else 'exited'
                if len(raw_out) >= 131072 or len(raw_err) >= 131072:
                    status = 'output_limit'
                observed = {'status': status, 'returncode': process.returncode,
                            'stdout_b64': base64.b64encode(raw_out).decode(),
                            'stderr_b64': base64.b64encode(raw_err).decode()}
            result = {'observed': observed, 'elapsed_seconds': time.monotonic() - started,
                      'candidate_executions': 1, 'python': sys.version.split()[0]}
            if coverage:
                report = scratch / 'coverage.json'
                try:
                    raw = report.read_bytes()
                    if len(raw) > 131072:
                        raise ValueError('Oversized coverage')
                    data = json.loads(raw)
                    if not valid_monitoring_coverage(data, source.decode('utf-8')):
                        raise ValueError('Invalid coverage')
                    available = data['intact'] and not data['limit_reached']
                except (OSError, ValueError, UnicodeError, RecursionError):
                    data, available = None, False
                result['coverage'] = {'available': available, 'data': data}
            return result
