"""Versioned Python-package tasks, separate from the frozen flat-module interface.

Dependencies and the JSON adapter are visible, immutable source. All source is
read-only during one isolated call; submitted repairs replace editable files
only. This backend does not install dependencies or enable model collection.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile

from vao.decisions.verification import sandbox_profile
from .environment import RepairTask, canonical, validate_cases
from .spectra import valid_coverage
from .verifier import RepairVerifier

VERSION = 2
MAX_FILES = 64
MAX_FILE_BYTES = 262144
MAX_TOTAL_BYTES = 2097152
IDENTIFIER = r'[A-Za-z_][A-Za-z0-9_]*'


def validate_workspace(editable, support):
    """Reject ambiguous modules, traversal, case aliases and incomplete packages."""
    if (not isinstance(editable, dict) or not isinstance(support, dict)
            or not 1 <= len(editable) <= 16 or len(editable) + len(support) > MAX_FILES
            or set(editable) & set(support)):
        raise ValueError('Invalid editable/support inventory')
    files = {**editable, **support}
    total, folded, modules = 0, set(), set()
    for name, source in files.items():
        if not isinstance(name, str) or not isinstance(source, str):
            raise ValueError('Source paths and text must be strings')
        if not re.fullmatch(rf'(?:{IDENTIFIER}/)*{IDENTIFIER}\.py', name):
            raise ValueError('Only canonical relative Python package paths are accepted')
        path = PurePosixPath(name)
        if any(part.startswith('__repair_') for part in path.parts):
            raise ValueError('Reserved verifier module name')
        if name.casefold() in folded:
            raise ValueError('Case-alias source paths')
        folded.add(name.casefold())
        module = name[:-3].replace('/', '.')
        if module.endswith('.__init__'):
            module = module[:-9]
        if module.casefold() in modules or name == '__init__.py':
            raise ValueError('Ambiguous package/module path')
        modules.add(module.casefold())
        for parent in path.parents:
            if parent != PurePosixPath('.') and str(parent / '__init__.py') not in files:
                raise ValueError('Explicit package initializer required')
        size = len(source.encode('utf-8'))
        if size > MAX_FILE_BYTES:
            raise ValueError('Package source exceeds per-file bound')
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ValueError('Package workspace exceeds total byte bound')
    # On case-insensitive hosts pkg/x.py and Pkg/y.py must not merge directories.
    directory_aliases = {}
    for name in files:
        for parent in PurePosixPath(name).parents:
            value = str(parent)
            if directory_aliases.setdefault(value.casefold(), value) != value:
                raise ValueError('Case-alias package directories')
    return files


def validate_public(public):
    if not isinstance(public, dict) or set(public) != {
            'schema_version', 'task_id', 'instruction', 'entrypoint', 'files',
            'support_files', 'public_cases', 'provenance'} or public['schema_version'] != VERSION:
        raise ValueError('Expected version-2 package public schema')
    files = validate_workspace(public['files'], public['support_files'])
    if not all(isinstance(public[k], str) and public[k] for k in ('task_id', 'instruction')):
        raise ValueError('Task identity and instruction required')
    entry = public['entrypoint']
    if (not isinstance(entry, dict) or set(entry) != {'module', 'function'}
            or not isinstance(entry['module'], str) or not isinstance(entry['function'], str)
            or not re.fullmatch(rf'{IDENTIFIER}(?:\.{IDENTIFIER})*', entry['module'])
            or not re.fullmatch(IDENTIFIER, entry['function'])):
        raise ValueError('Invalid package entrypoint')
    module = entry['module'].replace('.', '/')
    if module + '.py' not in files and module + '/__init__.py' not in files:
        raise ValueError('Entrypoint must be in the supplied workspace')
    validate_cases(public['public_cases'])
    if not isinstance(public['provenance'], dict) or not public['provenance'].get('kind'):
        raise ValueError('Task provenance kind required')
    canonical(public)
    return files


@dataclass(frozen=True)
class PackageTask(RepairTask):
    """Same observation contracts as RepairTask, with explicit package context."""

    @classmethod
    def from_dicts(cls, public, evaluator):
        validate_public(public)
        if not isinstance(evaluator, dict) or set(evaluator) != {'cases'}:
            raise ValueError('Unexpected evaluator schema')
        validate_cases(evaluator['cases'])
        return cls(canonical(public), canonical(evaluator))

    def validate_artifact(self, files):
        public = self.public
        validate_workspace(files, public['support_files'])
        if set(files) != set(public['files']):
            raise ValueError('Replace exactly the declared editable package files')


class PackageVerifier(RepairVerifier):
    """Fresh process/source tree per call; parent alone sees expected answers."""

    def __init__(self, public, timeout=5):
        super().__init__(timeout)
        validate_public(public)
        self.public = json.loads(canonical(public))

    def _execute(self, files, entrypoint, case, *, worker):
        if worker not in {'worker.py', 'coverage_worker.py'}:
            raise ValueError('Unsupported package execution mode')
        if entrypoint != self.public['entrypoint'] or set(files) != set(self.public['files']):
            raise ValueError('Call differs from the declared package task')
        workspace = validate_workspace(files, self.public['support_files'])
        with tempfile.TemporaryDirectory(prefix='repair-package-') as temp:
            work = Path(temp).resolve()
            source, scratch = work / 'source', work / 'scratch'
            source.mkdir(); scratch.mkdir()
            for name, content in workspace.items():
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            runner = source / '__repair_worker.py'
            shutil.copyfile(Path(__file__).with_name('package_worker.py'), runner)
            shutil.copyfile(Path(__file__).with_name('coverage_worker.py'), source / '__repair_coverage.py')
            payload = {'entrypoint': entrypoint, 'args': case['args'], 'kwargs': case.get('kwargs', {}),
                       'coverage_files': sorted(workspace)}
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(scratch), 'TMPDIR': str(scratch),
                   'PYTHONHASHSEED': '0', 'TZ': 'UTC', 'LANG': 'C'}
            profile = sandbox_profile(work) + f'(deny file-write* (subpath {json.dumps(str(source))}))'
            command = ['sandbox-exec', '-p', profile, sys.executable, '-I', str(runner),
                       'coverage' if worker == 'coverage_worker.py' else 'ordinary']
            with (work / 'stdout').open('w+b') as out, (work / 'stderr').open('w+b') as err:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                           cwd=source, env=env, start_new_session=True)
                timed_out = False
                try:
                    process.communicate(canonical(payload).encode(), timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                if timed_out:
                    return {'status': 'timeout'}
                if process.returncode != 0:
                    return {'status': 'worker_exit', 'returncode': process.returncode}
                out.seek(0)
                raw = out.read(131073)
                try:
                    result = json.loads(raw)
                    canonical(result)
                except (ValueError, UnicodeError, RecursionError):
                    return {'status': 'invalid_output'}
                return result if isinstance(result, dict) else {'status': 'invalid_output'}

    def coverage(self, files, entrypoint, case):
        workspace = validate_workspace(files, self.public['support_files'])
        result = self._execute(files, entrypoint, case, worker='coverage_worker.py')
        if (set(result) != {'observed', 'coverage'} or not isinstance(result['observed'], dict)
                or not valid_coverage(result['coverage'], workspace)):
            return {'available': False, 'reason': 'invalid_or_failed_coverage_worker', 'worker_result': result}
        data = result['coverage']
        complete = data['intact'] and not data['limit_reached']
        return {'available': complete, 'reason': None if complete else 'incomplete_coverage',
                'observed': self._observation(result['observed']), 'coverage': data}

    def preflight(self):
        """Verify denial on this backend, including immutable package sources."""
        with tempfile.TemporaryDirectory(prefix='repair-package-private-') as temp:
            sentinel = Path(temp) / 'private.txt'
            sentinel.write_text('evaluator-only-sentinel')
            code = '''import os, socket
from pathlib import Path
from .dependency import VALUE
def probe(path):
    checks = []
    actions = [lambda: open(path).read(),
               lambda: socket.socket().bind(('127.0.0.1', 0)),
               lambda: Path('pkg/dependency.py').write_text('VALUE = 99'),
               lambda: Path('pkg/dependency.py').chmod(0o777),
               lambda: Path('pkg').rename('moved')]
    for action in actions:
        try:
            action()
        except PermissionError:
            checks.append(True)
        else:
            checks.append(False)
    scratch = Path(os.environ['TMPDIR']) / 'allowed.txt'
    scratch.write_text('temporary')
    return checks + [VALUE == 7, scratch.read_text() == 'temporary',
                     not any('KEY' in k or 'TOKEN' in k for k in os.environ)]
'''
            public = {'schema_version': VERSION, 'task_id': 'synthetic-package-probe',
                      'instruction': 'Check isolation.', 'entrypoint': {'module': 'pkg.main', 'function': 'probe'},
                      'files': {'pkg/main.py': code},
                      'support_files': {'pkg/__init__.py': '', 'pkg/dependency.py': 'VALUE = 7\n'},
                      'public_cases': [{'id': 'probe', 'args': [str(sentinel)], 'expected': [True] * 8}],
                      'provenance': {'kind': 'synthetic_engineering_probe'}}
            probe = PackageVerifier(public, self.timeout)
            case = public['public_cases'][0]
            normal = probe.invoke(public['files'], public['entrypoint'], case)
            covered = probe.coverage(public['files'], public['entrypoint'], case)
        if normal != {'status': 'returned', 'value': [True] * 8} or not covered['available'] or covered['observed'] != normal:
            raise RuntimeError('Package sandbox preflight failed: ' + canonical([normal, covered]))
        return {'backend': 'macos-sandbox-exec', 'package_imports': True, 'source_writes_denied': True,
                'filesystem_denied': True, 'network_denied': True, 'credentials_absent': True,
                'scratch_writes_allowed': True, 'ordinary_coverage_agree': True,
                'executions': 2, 'python': sys.version.split()[0]}
