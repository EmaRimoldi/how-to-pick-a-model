"""Bounded public-failure coverage, prepared offline before any efficacy study.

All arms already know every public input, expectation and observed result.
This component acquires runtime evidence only, without an evaluator or reference.
"""

import json
import time

from .contrastive_diagnostics import compact_trace
from .diagnostics import binding, project as project_existing, selected_failure
from .environment import canonical

VERSION = 'public-failure-coverage-v1'
MAX_PUBLIC_CASES = 6


def select(public, files, observation, coverage):
    if coverage not in ('first', 'all'):
        raise ValueError('Expected first or all public failures')
    selected_failure(public, files, observation)  # Validate schema, binding and case order.
    if len(public['public_cases']) > MAX_PUBLIC_CASES:
        raise ValueError('Public suite exceeds the declared six-case acquisition bound')
    failures = [{'case': case, 'observed': row['observed']}
        for case, row in zip(public['public_cases'], observation['feedback']['cases'])
        if not row['passed']]
    return failures[:1] if coverage == 'first' else failures


def acquire(public, files, observation, verifier, *, coverage):
    started = time.monotonic()
    chosen = select(public, files, observation, coverage)
    result = {'version': VERSION, 'binding': observation['binding'], 'coverage': coverage,
        'selected_cases': [c['case']['id'] for c in chosen], 'records': [],
        'additional_executions': 0, 'available': False, 'complete': False}
    for item in chosen:
        ordinary = verifier.invoke(files, public['entrypoint'], item['case'])
        result['additional_executions'] += 1
        traced = verifier.trace(files, public['entrypoint'], item['case'])
        result['additional_executions'] += 1
        same = (traced.get('available') is True
            and canonical(item['observed']) == canonical(ordinary)
            and canonical(ordinary) == canonical(traced.get('observed')))
        result['records'].append({'case_id': item['case']['id'], 'available': same,
            'reason': None if same else 'trace_unavailable_or_observation_mismatch',
            'untraced_observation': ordinary, 'trace_result': traced})
    result['available'] = any(r['available'] for r in result['records'])
    result['complete'] = bool(chosen) and all(r['available'] for r in result['records'])
    result['reason'] = ('no_public_failure' if not chosen else
        None if result['complete'] else 'incomplete_runtime_coverage')
    result['diagnostic_seconds'] = time.monotonic() - started
    return result


def project(public, files, observation, diagnostic):
    chosen = select(public, files, observation, diagnostic['coverage'])
    expected_ids = [c['case']['id'] for c in chosen]
    if (diagnostic['version'] != VERSION or diagnostic['binding'] != binding(public, files)
        or diagnostic['selected_cases'] != expected_ids
        or [r['case_id'] for r in diagnostic['records']] != expected_ids):
        raise ValueError('Diagnostic does not cover the declared public state and cases')
    if (diagnostic['available'] != any(r['available'] for r in diagnostic['records'])
        or diagnostic['complete'] != (bool(chosen) and all(r['available'] for r in diagnostic['records']))
        or diagnostic['additional_executions'] != 2 * len(chosen)):
        raise ValueError('Diagnostic availability or execution accounting differs')
    request = project_existing(public, files, observation, 'focused')
    payload = json.loads(request['messages'][1]['content'])
    payload['runtime_diagnostic'] = {
        'version': VERSION, 'coverage': diagnostic['coverage'],
        'available': diagnostic['available'], 'complete': diagnostic['complete'],
        'reason': diagnostic['reason'],
        'trace_semantics': 'Observed runtime values, not expected values. With adjacent-reported-local-snapshot-delta-v1, apply locals_removed and locals_changed to the preceding reported snapshot; otherwise locals contains the retained snapshot. Explicit omissions remain unknown. Unavailable selected cases are retained without a trace.',
        'records': [{'case_id': r['case_id'], 'available': r['available'], 'reason': r['reason'],
            'trace': compact_trace(r['trace_result']['trace']) if r['available'] else None}
            for r in diagnostic['records']]}
    request['messages'][1]['content'] = canonical(payload)
    request['mode'] = 'offline_failure_coverage_preparation'
    return request
