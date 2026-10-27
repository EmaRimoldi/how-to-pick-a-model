"""One acquired public diagnostic, durably bound to its input and actual bytes.

Offline only. Loading/projecting never reacquires a trace. This prevents runtime
randomness from silently changing a reviewed request, without claiming that a
fresh execution would return identical intermediate values.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .diagnostics import acquire, binding, project, selected_failure
from .environment import canonical, identity
from .records import save
from .region_trace_worker import VERSION as TRACE_VERSION
from .region_verifier import valid_bounds

VERSION = 'single-public-acquisition-snapshot-v1'


def runtime():
    root = Path(__file__).resolve().parents[1]
    names = ['repair/acquisition_snapshot.py', 'repair/diagnostics.py', 'repair/environment.py',
             'repair/region_trace_worker.py', 'repair/region_verifier.py', 'repair/verifier.py',
             'repair/worker.py', 'decisions/verification.py']
    return {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names}


def context(public, files):
    return {key: (files if key == 'files' else public[key])
            for key in ('instruction', 'entrypoint', 'files', 'public_cases')}


def finite_seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(claim, snapshot, public, files, observation, *, expected_runtime=None):
    selected = selected_failure(public, files, observation)
    if (claim.get('version') != VERSION or claim.get('binding') != binding(public, files)
            or claim.get('public_context') != context(public, files)
            or claim.get('feedback') != observation['feedback'] or claim.get('api_calls') != 0
            or not finite_seconds(claim.get('shared_verification_seconds'))):
        raise ValueError('Acquisition claim does not match the public checkpoint')
    sources = claim.get('runtime')
    if (not isinstance(sources, dict) or set(sources) != set(runtime())
            or any(not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v) for v in sources.values())):
        raise ValueError('Invalid acquisition runtime identities')
    if expected_runtime is not None and sources != expected_runtime:
        raise ValueError('Acquisition runtime differs from the declared freeze')
    if (snapshot.get('version') != VERSION or snapshot.get('claim_id') != identity(claim)
            or snapshot.get('snapshot_id') != identity({k: v for k, v in snapshot.items() if k != 'snapshot_id'})):
        raise ValueError('Acquisition snapshot identity differs')
    diagnostic = snapshot['diagnostic']
    if (diagnostic.get('binding') != claim['binding'] or type(diagnostic.get('available')) is not bool
            or not finite_seconds(diagnostic.get('diagnostic_seconds'))
            or diagnostic.get('additional_executions') != (2 if selected else 0)):
        raise ValueError('Invalid acquisition resource accounting or binding')
    if selected is None:
        if diagnostic['available'] or diagnostic.get('reason') != 'no_public_failure':
            raise ValueError('A public pass cannot claim a diagnostic')
        return diagnostic
    if diagnostic.get('case_id') != selected['case']['id']:
        raise ValueError('Acquisition does not use the declared first public failure')
    traced, ordinary = diagnostic.get('trace_result', {}), diagnostic.get('untraced_observation')
    trace = traced.get('trace')
    if trace is not None:
        if (not isinstance(trace, dict) or trace.get('version') != TRACE_VERSION
                or not isinstance(trace.get('events'), list) or len(trace['events']) > 32
                or type(trace.get('intact')) is not bool or len(canonical(trace).encode()) > 16384
                or not valid_bounds(trace, files)):
            raise ValueError('Stored trace violates the declared representation')
        if traced.get('available') != trace['intact']:
            raise ValueError('Stored trace availability differs from integrity flag')
    same = (traced.get('available') is True and trace is not None
            and canonical(selected['observed']) == canonical(ordinary) == canonical(traced.get('observed')))
    if diagnostic['available'] != same or diagnostic['reason'] != (None if same else 'trace_unavailable_or_observation_mismatch'):
        raise ValueError('Stored diagnostic invents or hides observation agreement')
    return diagnostic


def acquire_once(output, public, files, observation, verifier):
    """Claim a fresh directory before executing; never resume or overwrite it.

    The verifier must supply the versioned balanced representation. Both success
    and unavailable diagnostics are sealed. An interrupted acquisition keeps its
    claim, without inventing a trace, timing, or successful completion.
    """
    selected_failure(public, files, observation)
    claim = {'version': VERSION, 'binding': binding(public, files),
             'public_context': context(public, files), 'feedback': observation['feedback'],
             'shared_verification_seconds': observation['verifier_seconds'],
             'runtime': runtime(), 'api_calls': 0}
    if not finite_seconds(claim['shared_verification_seconds']):
        raise ValueError('Missing shared verification timing')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    save(output/'claim.json', claim)
    try:
        diagnostic = acquire(public, files, observation, verifier)
        snapshot = {'version': VERSION, 'claim_id': identity(claim), 'diagnostic': diagnostic,
                    'api_calls': 0, 'mode': 'offline_diagnostic_preparation'}
        snapshot['snapshot_id'] = identity(snapshot)
        validate(claim, snapshot, public, files, observation, expected_runtime=runtime())
        save(output/'snapshot.json', snapshot)
        save(output/'completion.json', {'claim_id': identity(claim), 'snapshot_id': snapshot['snapshot_id']})
    except BaseException as exc:
        save(output/'interruption.json', {'exception_type': type(exc).__name__, 'api_calls': 0,
             'completed': False, 'resume_allowed': False,
             'local_resources': 'May be partially consumed; no successful acquisition or zero local cost inferred.'})
        raise
    return snapshot


def load(output, public, files, observation, *, expected_runtime=None):
    root = Path(output)
    if (root/'interruption.json').exists() or not (root/'completion.json').exists():
        raise ValueError('Acquisition has no uninterrupted completion')
    claim, snapshot, seal = [json.loads((root/name).read_text()) for name in ('claim.json', 'snapshot.json', 'completion.json')]
    validate(claim, snapshot, public, files, observation, expected_runtime=expected_runtime)
    if seal != {'claim_id': identity(claim), 'snapshot_id': snapshot['snapshot_id']}:
        raise ValueError('Acquisition completion identity differs')
    return snapshot


def projected(output, public, files, observation, arm, *, expected_runtime=None):
    """Load a sealed snapshot and project exact stored bytes, with no execution.

    The final collector must bind the exact snapshot ID and projected messages
    into its separately authorized source/request freeze. This helper is not a
    funding mechanism or a trust certificate for candidate-generated values.
    """
    if arm not in ('focused', 'focused_trace'):
        raise ValueError('Expected a matched feedback or trace arm')
    snapshot = load(output, public, files, observation, expected_runtime=expected_runtime)
    return project(public, files, observation, arm, snapshot['diagnostic'])
