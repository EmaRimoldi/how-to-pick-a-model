"""Public-only coverage, unavailable evidence, stale checkpoints and full costs."""
from copy import deepcopy
import json

import pytest

from vao.repair.diagnostics import binding, project as baseline
from vao.repair.failure_coverage_diagnostics import acquire, project, select


def state():
    public = {'schema_version': 1, 'task_id': 'synthetic/coverage',
        'instruction': 'Return the input.', 'entrypoint': {'module': 'solution', 'function': 'solve'},
        'files': {'solution.py': 'def solve(x): return 0\n'}, 'provenance': {},
        'public_cases': [{'id': str(i), 'args': [i], 'expected': i} for i in range(3)]}
    rows = [{'id': str(i), 'passed': i == 0, 'observed': {'status': 'returned', 'value': 0}} for i in range(3)]
    observation = {'binding': binding(public, public['files']),
        'feedback': {'passed': False, 'passed_cases': 1, 'total_cases': 3, 'cases': rows}}
    return public, public['files'], observation


class StubVerifier:
    def __init__(self, unavailable=None):
        self.calls = []
        self.unavailable = unavailable

    def invoke(self, files, entrypoint, case):
        self.calls.append(('ordinary', case['id']))
        return {'status': 'returned', 'value': 0}

    def trace(self, files, entrypoint, case):
        self.calls.append(('trace', case['id']))
        return {'available': case['id'] != self.unavailable,
            'observed': {'status': 'returned', 'value': 0}, 'trace': {'events': []}}


def test_all_failures_add_runtime_only_and_charge_each_execution():
    public, files, observation = state()
    v = StubVerifier()
    first = acquire(public, files, observation, v, coverage='first')
    all_failed = acquire(public, files, observation, v, coverage='all')
    assert first['selected_cases'] == ['1']
    assert all_failed['selected_cases'] == ['1', '2']
    assert first['records'][0] == all_failed['records'][0]
    assert first['additional_executions'] == 2
    assert all_failed['additional_executions'] == 4
    assert len(v.calls) == 6
    core = json.loads(baseline(public, files, observation, 'focused')['messages'][1]['content'])
    for diagnostic in (first, all_failed):
        request = project(public, files, observation, diagnostic)
        payload = json.loads(request['messages'][1]['content'])
        payload.pop('runtime_diagnostic')
        assert payload == core
        assert request['provider_call_enabled'] is False


def test_unavailable_selected_case_is_retained_and_never_retried():
    public, files, observation = state()
    v = StubVerifier(unavailable='2')
    diagnostic = acquire(public, files, observation, v, coverage='all')
    assert diagnostic['available'] is True and diagnostic['complete'] is False
    assert diagnostic['additional_executions'] == len(v.calls) == 4
    runtime = json.loads(project(public, files, observation, diagnostic)['messages'][1]['content'])['runtime_diagnostic']
    assert [r['case_id'] for r in runtime['records']] == ['1', '2']
    assert runtime['records'][1]['trace'] is None
    forged = deepcopy(diagnostic); forged['complete'] = True
    with pytest.raises(ValueError, match='availability'):
        project(public, files, observation, forged)


def test_updated_artifact_needs_new_feedback_and_private_fields_are_rejected():
    public, files, observation = state()
    changed = {'solution.py': 'def solve(x): return 1\n'}
    with pytest.raises(ValueError, match='different public state'):
        select(public, changed, observation, 'all')
    private = dict(public, evaluator={'secret': 'not permitted'})
    with pytest.raises(ValueError, match='public task schema'):
        select(private, files, observation, 'first')
    reordered = deepcopy(observation); reordered['feedback']['cases'].reverse()
    with pytest.raises(ValueError, match='ordered public suite'):
        select(public, files, reordered, 'all')


def test_no_failure_means_no_acquisition_or_invented_trace():
    public, files, observation = state()
    for row in observation['feedback']['cases']:
        row['passed'] = True
        row['observed']['value'] = int(row['id'])
    observation['feedback'].update(passed=True, passed_cases=3)
    v = StubVerifier()
    diagnostic = acquire(public, files, observation, v, coverage='all')
    assert not v.calls and diagnostic['additional_executions'] == 0
    assert diagnostic['reason'] == 'no_public_failure'
    assert not diagnostic['available'] and not diagnostic['records']


def test_suite_bound_is_checked_before_any_execution():
    public, files, observation = state()
    for i in range(3, 7):
        public['public_cases'].append({'id': str(i), 'args': [i], 'expected': i})
        observation['feedback']['cases'].append({'id': str(i), 'passed': False,
            'observed': {'status': 'returned', 'value': 0}})
    observation['binding'] = binding(public, files)
    observation['feedback']['total_cases'] = 7
    v = StubVerifier()
    with pytest.raises(ValueError, match='six-case'):
        acquire(public, files, observation, v, coverage='all')
    assert not v.calls
