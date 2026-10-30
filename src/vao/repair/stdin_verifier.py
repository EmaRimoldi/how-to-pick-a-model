"""Isolated whole-program execution preserving exact stdin and stdout bytes.

This engineering backend does not define a dataset comparator, suite split,
qualification rule or paid collection. Expectations stay in the parent.
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
from .spectra import valid_coverage
from .coverage_worker import VERSION as FUNCTION_COVERAGE_VERSION


def valid_stdin_coverage(data, source):
    """Reuse location bounds but keep whole-program coverage a distinct version."""
    return (isinstance(data, dict) and data.get('version') == 'stdin-main-line-coverage-v1'
            and valid_coverage({**data, 'version': FUNCTION_COVERAGE_VERSION}, {'main.py': source}))


def compare_stdout(observed: dict, expected: bytes, *, mode: str) -> bool:
    """Explicit comparison: no float coercion or implicit Python-version fallback."""
    if mode not in {'exact_bytes', 'ascii_whitespace_tokens'}:
        raise ValueError('Unknown stdout comparator')
    if not isinstance(expected, bytes):
        raise ValueError('Expected output must be bytes')
    if observed.get('status') != 'exited' or observed.get('returncode') != 0:
        return False
    try:
        actual = base64.b64decode(observed['stdout_b64'], validate=True)
    except (KeyError, ValueError, TypeError):
        return False
    return actual == expected if mode == 'exact_bytes' else actual.split() == expected.split()


class StdinVerifier:
    """Fresh native sandbox per input; immutable sources, clean env and bounded IO."""

    def __init__(self, timeout: float = 5):
        if sys.platform != 'darwin' or not shutil.which('sandbox-exec'):
            raise RuntimeError('stdin program execution requires macOS sandbox-exec')
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError('Timeout must be between 0 and 30 seconds')
        self.timeout = timeout

    def invoke(self, source: bytes, stdin: bytes, *, coverage: bool = False) -> dict:
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
            for original, local in [('stdin_worker.py', '__repair_worker.py'),
                                    ('coverage_worker.py', '__repair_coverage.py')]:
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
                    if not valid_stdin_coverage(data, source.decode('utf-8')):
                        raise ValueError('Invalid coverage')
                    available = data['intact'] and not data['limit_reached']
                except (OSError, ValueError, UnicodeError, RecursionError):
                    data, available = None, False
                result['coverage'] = {'available': available, 'data': data}
            return result

    def preflight(self):
        with tempfile.TemporaryDirectory(prefix='repair-stdin-private-') as temp:
            sentinel = Path(temp) / 'private.txt'; sentinel.write_text('private-answer')
            program = b'''import os, socket, sys
from pathlib import Path
path = sys.stdin.buffer.read().decode()
checks = []
for action in [lambda: open(path).read(), lambda: socket.socket().bind(('127.0.0.1', 0)),
               lambda: Path('main.py').write_text('changed'), lambda: Path('main.py').chmod(0o777),
               lambda: Path.cwd().rename(Path.cwd().parent / 'moved')]:
    try: action()
    except PermissionError: checks.append(True)
    else: checks.append(False)
checks.append(not any('KEY' in k or 'TOKEN' in k for k in os.environ))
scratch = Path(os.environ['TMPDIR']) / 'allowed'
scratch.write_bytes(b'allowed'); checks.append(scratch.read_bytes() == b'allowed')
print(checks)
'''
            regular = self.invoke(program, str(sentinel).encode())
            traced = self.invoke(program, str(sentinel).encode(), coverage=True)
            expected = (str([True] * 7) + '\n').encode()
            if (not compare_stdout(regular['observed'], expected, mode='exact_bytes')
                    or not compare_stdout(traced['observed'], expected, mode='exact_bytes')
                    or not traced['coverage']['available']):
                raise RuntimeError('stdin sandbox preflight failed')
        return {'backend': 'macos-sandbox-exec', 'filesystem_denied': True,
                'network_denied': True, 'credentials_absent': True,
                'source_writes_denied': True, 'scratch_writes_allowed': True,
                'ordinary_coverage_agree': True, 'candidate_executions': 2,
                'python': sys.version.split()[0]}
