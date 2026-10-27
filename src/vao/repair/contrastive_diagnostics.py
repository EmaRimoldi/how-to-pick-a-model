"""Offline v2 diagnostic: bounded failing/passing traces, without new test oracles.

Not a collector or fitted policy. Historical acquisition/worker code is unchanged.
"""

from fractions import Fraction
import json
import time

from .diagnostics import binding, project as project_existing, selected_failure
from .environment import canonical


def shape(value):
    if type(value) is list:
        return ['list', [shape(v) for v in value]]
    if type(value) is dict:
        return ['dict', {k: shape(v) for k, v in sorted(value.items())}]
    return type(value).__name__


def case_input(case):
    return {'args': case['args'], 'kwargs': case.get('kwargs', {})}


def input_distance(left, right):
    """Mean normalized leaf edit distance; serialization punctuation contributes zero."""
    if type(left) is not type(right):
        return Fraction(1)
    if type(left) is str:
        left, right = left[:256], right[:256]
        previous = list(range(len(right) + 1))
        for i, a in enumerate(left, 1):
            current = [i]
            for j, b in enumerate(right, 1):
                current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
            previous = current
        return Fraction(previous[-1], max(len(left), len(right), 1))
    if type(left) is list:
        values = [input_distance(a, b) for a, b in zip(left, right)]
        values += [Fraction(1)] * abs(len(left) - len(right))
    elif type(left) is dict:
        values = [input_distance(left[k], right[k]) if k in left and k in right else Fraction(1)
            for k in sorted(set(left) | set(right))]
    else:
        return Fraction(left != right)
    return sum(values, Fraction(0)) / max(len(values), 1)


def input_truncated(value):
    if type(value) is str:
        return len(value) > 256
    if type(value) is list:
        return any(input_truncated(v) for v in value)
    if type(value) is dict:
        return any(input_truncated(v) for v in value.values())
    return False


def select_pair(public, files, observation):
    """First failure plus closest already-passing PUBLIC input; deterministic ties.

    Prefer identical recursive input type shapes, then lowest mean normalized
    leaf Levenshtein distance on at most the first 256 characters per string. Ties
    keep public order. Expected answers, case names and evaluator data never rank.
    This similarity is a heuristic, not semantic distance or learned selection.
    """
    failure = selected_failure(public, files, observation)
    if failure is None:
        return None
    target = case_input(failure['case'])
    candidates = []
    for index, (case, row) in enumerate(zip(public['public_cases'], observation['feedback']['cases'])):
        if not row['passed']:
            continue
        inputs = case_input(case)
        ratio = 1 - input_distance(target, inputs)
        same_shape = shape(inputs) == shape(target)
        candidates.append((same_shape, ratio, -index, case, row))
    if not candidates:
        return {'failure': failure, 'passing': None, 'selection': None}
    same_shape, ratio, _, case, row = max(candidates, key=lambda item: item[:3])
    return {'failure': failure, 'passing': {'case': case, 'observed': row['observed']},
        'selection': {'same_input_shape': same_shape, 'similarity': [ratio.numerator, ratio.denominator],
            'string_character_limit': 256, 'passing_input_truncated': input_truncated(case_input(case)),
            'failing_input_truncated': input_truncated(target)}}


def compact_trace(trace):
    """Lossless delta encoding of retained local snapshots, not causal slicing.

    Never restores dropped events or omitted values. Changes refer to the preceding
    reported snapshot, not a persistent frame identity (recursion is permitted).
    """
    result = {k: v for k, v in trace.items() if k != 'events'}
    result['encoding'] = 'adjacent-reported-local-snapshot-delta-v1'
    previous = {}
    events = []
    for event in trace['events']:
        current = event['locals']
        row = {k: v for k, v in event.items() if k != 'locals'}
        row['locals_changed'] = {k: v for k, v in current.items()
            if k not in previous or canonical(previous[k]) != canonical(v)}
        row['locals_removed'] = sorted(set(previous) - set(current))
        events.append(row)
        previous = current
    result['events'] = events
    return result if len(canonical(result).encode()) < len(canonical(trace).encode()) else trace


def expand_trace(trace):
    """Exact structural replay of the retained snapshots for representation QA."""
    if 'encoding' not in trace:
        return trace
    if trace['encoding'] != 'adjacent-reported-local-snapshot-delta-v1':
        raise ValueError('Unknown trace encoding')
    result = {k: v for k, v in trace.items() if k not in ('events', 'encoding')}
    previous = {}
    events = []
    for event in trace['events']:
        current = dict(previous)
        for name in event['locals_removed']:
            del current[name]
        current.update(event['locals_changed'])
        row = {k: v for k, v in event.items() if k not in ('locals_changed', 'locals_removed')}
        row['locals'] = current
        events.append(row)
        previous = current
    result['events'] = events
    return result


def acquire(public, files, observation, verifier, *, paired):
    """Pay two executions per selected case and check unchanged public observation."""
    start = time.monotonic()
    pair = select_pair(public, files, observation)
    result = {'version': 'contrastive-public-trace-v2', 'binding': observation['binding'],
        'paired': paired, 'available': False, 'reason': 'no_public_failure',
        'additional_executions': 0, 'records': [], 'selection': pair['selection'] if pair else None}
    if pair is not None:
        selected = [('failure', pair['failure'])]
        if paired and pair['passing'] is not None:
            selected.append(('passing', pair['passing']))
        for role, item in selected:
            ordinary = verifier.invoke(files, public['entrypoint'], item['case'])
            result['additional_executions'] += 1
            traced = verifier.trace(files, public['entrypoint'], item['case'])
            result['additional_executions'] += 1
            same = (traced.get('available') is True and canonical(item['observed']) == canonical(ordinary)
                and canonical(ordinary) == canonical(traced.get('observed')))
            result['records'].append({'role': role, 'case_id': item['case']['id'], 'available': same,
                'untraced_observation': ordinary, 'trace_result': traced})
        result['available'] = all(r['available'] for r in result['records']) and (not paired or pair['passing'] is not None)
        result['reason'] = None if result['available'] else ('no_passing_public_case' if paired and pair['passing'] is None else 'trace_unavailable_or_observation_mismatch')
    result['diagnostic_seconds'] = time.monotonic() - start
    return result


def project(public, files, observation, diagnostic):
    """Add only validated public runtime data; never a generated expected answer."""
    if diagnostic['binding'] != binding(public, files):
        raise ValueError('Diagnostic belongs to a different public state')
    request = project_existing(public, files, observation, 'focused')
    payload = json.loads(request['messages'][1]['content'])
    payload['runtime_diagnostic'] = {'version': diagnostic['version'], 'available': diagnostic['available'],
        'reason': diagnostic['reason'],
        'trace_semantics': 'When encoding is adjacent-reported-local-snapshot-delta-v1, apply locals_removed and locals_changed to the preceding reported snapshot; otherwise locals is a complete retained snapshot. Values are observed, not expected. A passing case is one public example, not proof of correctness.',
        'records': [{'role': r['role'], 'case_id': r['case_id'], 'trace': compact_trace(r['trace_result']['trace'])}
            for r in diagnostic['records']] if diagnostic['available'] else []}
    request['messages'][1]['content'] = canonical(payload)
    request['mode'] = 'offline_contrastive_diagnostic_preparation'
    return request
