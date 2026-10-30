import copy
import json

import pytest

from vao.repair.diagnostics import binding
from vao.repair.environment import canonical
from vao.repair.spectrum_ablation import project, triplet
from vao.repair.coverage_worker import VERSION, EVENT_LIMIT, LINE_LIMIT


def inputs():
    public = {'schema_version': 1, 'task_id': 'DO_NOT_SEND_ID', 'instruction': 'Return zero.',
        'entrypoint': {'module': 'solution', 'function': 'solve'},
        'files': {'solution.py': 'def solve(x):\n    if x:\n        return 1\n    return 0\n'},
        'provenance': {'kind': 'synthetic', 'private_url': 'DO_NOT_SEND_PROVENANCE'},
        'public_cases': [{'id': 'f', 'args': [1], 'expected': 0}, {'id': 'p', 'args': [0], 'expected': 0}]}
    rows = []; outcomes = []
    for case, value, lines in zip(public['public_cases'], [1, 0], [[2, 3], [2, 4]]):
        observation = {'status': 'returned', 'value': value}
        outcomes.append({'id': case['id'], 'passed': value == 0, 'observed': observation})
        rows.append({'id': case['id'], 'ordinary': observation, 'stored_observed': observation,
            'stored_passed': value == 0, 'coverage_result': {'available': True,
                'observed': observation, 'coverage': {'version': VERSION,
                    'lines': [['solution.py', n] for n in lines], 'line_events': len(lines),
                    'limit_reached': False, 'intact': True, 'event_limit': EVENT_LIMIT, 'line_limit': LINE_LIMIT}}})
    key = binding(public, public['files'])
    stored = {'binding': key, 'feedback': {'passed': False, 'passed_cases': 1, 'total_cases': 2, 'cases': outcomes}}
    acquired = {'binding': key, 'cases': rows, 'additional_executions': 4, 'seconds': 1.0}
    return public, stored, acquired


def payload(request):
    return json.loads(request['messages'][1]['content'])


def test_triplet_has_same_shared_inputs_and_canonical_not_score_order():
    requests = triplet(*inputs())
    f, n, s = (payload(requests[a]) for a in ('feedback', 'neutral', 'scored'))
    assert f == {k: v for k, v in n.items() if k != 'source_excerpts'}
    assert f == {k: v for k, v in s.items() if k != 'source_excerpts'}
    locations = s['source_excerpts']['locations']
    assert [row['line'] for row in locations] == [2, 3, 4]
    assert [row['squared_ochiai'] for row in locations] == [[1, 2], [1, 1], [0, 1]]
    assert {r['messages'][0]['content'] for r in requests.values()} == {requests['feedback']['messages'][0]['content']}
    assert all(r['provider_call_enabled'] is False for r in requests.values())


def test_neutral_erases_outcome_association_even_when_coverage_changes():
    p, o, a = inputs()
    first = project(p, o, 'neutral', a)
    modified = copy.deepcopy(a)
    modified['cases'][1]['coverage_result']['coverage']['lines'] = [['solution.py', n] for n in [2, 3, 4]]
    modified['cases'][1]['coverage_result']['coverage']['line_events'] = 3
    assert project(p, o, 'neutral', modified) == first
    assert project(p, o, 'scored', modified) != project(p, o, 'scored', a)
    for row in payload(first)['source_excerpts']['locations']:
        assert all(row[k] == 'not supplied' for k in ('failing_covered', 'passing_covered', 'squared_ochiai'))


def test_private_metadata_and_cached_diagnostics_never_enter_any_prompt():
    p, o, a = inputs()
    a['evaluator'] = 'SECRET_EVALUATOR'
    a['ranking'] = 'SECRET_CACHED_RANKING'
    a['seconds'] = 12345.6789
    requests = triplet(p, o, a)
    assert all(marker not in canonical(requests) for marker in (
        'DO_NOT_SEND_ID', 'DO_NOT_SEND_PROVENANCE', 'SECRET_EVALUATOR', 'SECRET_CACHED_RANKING', '12345.6789'))
    p['evaluator'] = {'cases': []}
    with pytest.raises(ValueError, match='public task schema'):
        triplet(p, o, a)


@pytest.mark.parametrize('mutation', ['files', 'labels', 'aggregate', 'extra_feedback', 'missing_case', 'coverage_baseline'])
def test_stale_inconsistent_or_extra_feedback_rejected(mutation):
    p, o, a = inputs()
    if mutation == 'files':
        p['files']['solution.py'] += '# revised\n'
    elif mutation == 'labels':
        o['feedback']['cases'][0]['passed'] = True
    elif mutation == 'aggregate':
        o['feedback']['passed_cases'] = 2
    elif mutation == 'extra_feedback':
        o['feedback']['private_correctness'] = True
    elif mutation == 'missing_case':
        o['feedback']['cases'].pop()
    else:
        a['cases'][0]['stored_observed'] = {'status': 'returned', 'value': 3}
    with pytest.raises(ValueError):
        triplet(p, o, a)


def test_incomplete_coverage_is_shared_missing_information_not_case_exclusion():
    p, o, a = inputs()
    a['cases'][0]['coverage_result']['coverage']['intact'] = False
    requests = triplet(p, o, a)
    n, s = (payload(requests[arm])['source_excerpts'] for arm in ('neutral', 'scored'))
    assert n == s == {'available': False, 'reason': 'incomplete_or_inconsistent_coverage', 'locations': None}
    assert len(payload(requests['scored'])['public_cases']) == 2


def test_flat_spectrum_keeps_all_tied_locations():
    p, o, a = inputs()
    for row in a['cases']:
        row['coverage_result']['coverage']['lines'] = [['solution.py', n] for n in [2, 3, 4]]
        row['coverage_result']['coverage']['line_events'] = 3
    s = payload(triplet(p, o, a)['scored'])['source_excerpts']
    assert len(s['locations']) == 3
    assert all(row['squared_ochiai'] == [1, 2] for row in s['locations'])


def test_unavailable_acquisition_and_actual_worker_failure_are_retained():
    p, o, a = inputs()
    o['feedback']['cases'][0]['observed'] = {'status': 'worker_exit', 'returncode': 1}
    requests = triplet(p, o, None)
    assert payload(requests['feedback'])['latest_feedback']['cases'][0]['observed']['returncode'] == 1
    assert payload(requests['scored'])['source_excerpts']['reason'] == 'not_acquired'


def test_public_passing_state_is_not_a_recovery_checkpoint():
    p, o, a = inputs()
    o['feedback']['cases'][0].update(passed=True, observed={'status': 'returned', 'value': 0})
    o['feedback'].update(passed=True, passed_cases=2)
    with pytest.raises(ValueError, match='public-failing checkpoint'):
        triplet(p, o, a)
