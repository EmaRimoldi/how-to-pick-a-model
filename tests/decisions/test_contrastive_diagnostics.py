"""Public-only contrasting inputs and lossless bounded trace representation."""
from copy import deepcopy
import json
import sys
import hashlib
from pathlib import Path
import zipfile

import pytest

from vao.repair.contrastive_diagnostics import acquire, compact_trace, expand_trace, input_distance, project, select_pair
from vao.repair.diagnostics import binding


def fixture():
    public = {'schema_version': 1, 'task_id': 'engineering/contrast', 'instruction': 'Return the input',
        'entrypoint': {'module': 'solution', 'function': 'solve'},
        'files': {'solution.py': 'def solve(x): return x'},
        'public_cases': [{'id': 'fail', 'args': ['abcd'], 'expected': 'abcd'},
            {'id': 'far', 'args': [None], 'expected': None},
            {'id': 'near', 'args': ['abce'], 'expected': 'abce'},
            {'id': 'tie', 'args': ['abce'], 'expected': 'abce'}],
        'provenance': {'SECRET_CANARY': 'do not project'}}
    obs = {'binding': binding(public, public['files']), 'feedback': {'passed': False,
        'passed_cases': 3, 'total_cases': 4, 'cases': [{'id': c['id'], 'passed': i > 0,
            'observed': {'status': 'returned', 'value': 'bad' if i == 0 else c['args'][0]}}
            for i, c in enumerate(public['public_cases'])]}}
    return public, obs


class Verifier:
    def __init__(self):
        self.calls = []

    def invoke(self, files, entrypoint, case):
        self.calls.append(('ordinary', case['id']))
        return {'status': 'returned', 'value': 'bad' if case['id'] == 'fail' else case['args'][0]}

    def trace(self, files, entrypoint, case):
        self.calls.append(('trace', case['id']))
        return {'available': True, 'observed': {'status': 'returned', 'value': 'bad' if case['id'] == 'fail' else case['args'][0]},
            'trace': {'events': [], 'events_dropped': 0, 'intact': True}}


def test_pair_choice_uses_inputs_and_public_passes_with_ordered_ties():
    public, obs = fixture()
    pair = select_pair(public, public['files'], obs)
    assert pair['passing']['case']['id'] == 'near'
    assert pair['selection']['same_input_shape']
    changed = deepcopy(public)
    changed['public_cases'][2]['expected'] = 'ORACLE_CANARY'
    obs['binding'] = binding(changed, changed['files'])
    assert select_pair(changed, changed['files'], obs)['passing']['case']['id'] == 'near'
    changed['evaluator'] = {'cases': []}
    with pytest.raises(ValueError, match='public task schema'):
        select_pair(changed, changed['files'], obs)


def test_input_distance_ignores_shared_json_scaffolding_and_preserves_types():
    assert input_distance({'args': ['abcd'], 'kwargs': {}}, {'args': ['abce'], 'kwargs': {}}) < input_distance(
        {'args': ['abcd'], 'kwargs': {}}, {'args': [''], 'kwargs': {}})
    assert input_distance(True, 1) == 1
    assert input_distance('kitten', 'sitting').numerator == 3
    assert input_distance('kitten', 'sitting').denominator == 7
    assert input_distance([], []) == 0


def test_delta_encoding_replays_recursion_deletion_omissions_and_exception_exit():
    trace = {'events_dropped': 8, 'events': [
        {'file': 'solution.py', 'function': 'recur', 'line': 1, 'event': 'line', 'locals': {'n': 2, 'm': {'omitted': 'object_or_depth_limit'}}},
        {'file': 'solution.py', 'function': 'recur', 'line': 1, 'event': 'line', 'locals': {'n': 1}},
        {'file': 'solution.py', 'function': 'recur', 'line': 2, 'event': 'exception', 'exception': 'ValueError', 'locals': {'n': 1}},
        {'file': 'solution.py', 'function': 'recur', 'line': 2, 'event': 'return', 'returned': None, 'locals': {'n': 1}},
        {'file': 'solution.py', 'function': 'recur', 'line': 3, 'event': 'line', 'locals': {'n': 2, 'm': None}},
    ]}
    packed = compact_trace(trace)
    assert expand_trace(packed) == trace
    from vao.repair.environment import canonical
    assert len(canonical(packed).encode()) <= len(canonical(trace).encode())
    # Longer repeated snapshots force the delta path as well as the raw fallback.
    repeated = {'events': [{'event': 'line', 'locals': {'x': 'a' * 96, 'y': 'b' * 96}}] * 20}
    assert compact_trace(repeated)['encoding'] == 'adjacent-reported-local-snapshot-delta-v1'
    assert expand_trace(compact_trace(repeated)) == repeated
    typed = {'events': [{'event': 'line', 'locals': {'long': 'a' * 96, 'x': v, 'nested': {'items': [v], 'length': 1}}}
        for v in (1, True, 1.0, 1, 1.0, True)]}
    assert compact_trace(typed)['encoding'] == 'adjacent-reported-local-snapshot-delta-v1'
    assert canonical(expand_trace(compact_trace(typed))) == canonical(typed)


def test_acquisition_accounts_for_both_executions_and_projection_keeps_core():
    public, obs = fixture()
    a, b = Verifier(), Verifier()
    single = acquire(public, public['files'], obs, a, paired=False)
    pair = acquire(public, public['files'], obs, b, paired=True)
    assert single['additional_executions'] == len(a.calls) == 2
    assert pair['additional_executions'] == len(b.calls) == 4
    outputs = [project(public, public['files'], obs, d) for d in (single, pair)]
    payloads = [json.loads(o['messages'][1]['content']) for o in outputs]
    assert len(payloads[0].pop('runtime_diagnostic')['records']) == 1
    assert len(payloads[1].pop('runtime_diagnostic')['records']) == 2
    assert payloads[0] == payloads[1]
    assert all(not o['provider_call_enabled'] and 'SECRET_CANARY' not in json.dumps(o) for o in outputs)


def test_mismatch_suppresses_all_traces_and_no_failure_costs_nothing():
    public, obs = fixture()
    changed = Verifier()
    changed.trace = lambda *args: {'available': True, 'observed': {'status': 'returned', 'value': 'MISMATCH'}, 'trace': {'events': ['DO_NOT_PROJECT']}}
    result = acquire(public, public['files'], obs, changed, paired=True)
    assert not result['available'] and result['additional_executions'] == 4
    assert 'DO_NOT_PROJECT' not in json.dumps(project(public, public['files'], obs, result))
    for row in obs['feedback']['cases']:
        row['passed'] = True
    verifier = Verifier()
    result = acquire(public, public['files'], obs, verifier, paired=True)
    assert result['reason'] == 'no_public_failure' and not verifier.calls


def test_no_passing_case_is_retained_as_unavailable_not_invented():
    public, obs = fixture()
    for row in obs['feedback']['cases']:
        row['passed'] = False
    result = acquire(public, public['files'], obs, Verifier(), paired=True)
    assert not result['available'] and result['reason'] == 'no_passing_public_case'
    assert result['additional_executions'] == 2
    assert len(result['records']) == 1


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires the macOS isolation backend')
def test_real_sandbox_pair_preserves_public_observations():
    from vao.repair.diagnostics import observe
    from vao.repair.verifier import RepairVerifier
    public, _ = fixture()
    public['files']['solution.py'] = 'def solve(x):\n    return x[:-1] if isinstance(x, str) and x.endswith("d") else x\n'
    verifier = RepairVerifier()
    verifier.preflight()
    observation = observe(public, public['files'], verifier)
    result = acquire(public, public['files'], observation, verifier, paired=True)
    assert result['available'] and result['additional_executions'] == 4
    assert [r['case_id'] for r in result['records']] == ['fail', 'near']
    for record in result['records']:
        trace = record['trace_result']['trace']
        assert expand_trace(compact_trace(trace)) == trace
    assert not project(public, public['files'], observation, result)['provider_call_enabled']


def test_published_public_records_replay_all_projections_and_preserve_sources():
    source = Path(__file__).resolve().parents[2] / 'experiments/python-repair/checkpoint-environment/results/contrastive-preparation-20261026'
    manifest = json.loads((source / 'manifest.json').read_text())
    assert hashlib.sha256((source / 'records.zip').read_bytes()).hexdigest() == manifest['archive_sha256']
    with zipfile.ZipFile(source / 'records.zip') as archive:
        assert set(archive.namelist()) == set(manifest['files'])
        for name, expected in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        records = [json.loads(archive.read(name)) for name in sorted(archive.namelist()) if name.startswith('task-')]
        assert len(records) == 12
        executions = 0
        available = 0
        for record in records:
            public, obs = record['public'], record['observation']
            for label in ('single', 'paired'):
                variant = record[label]
                diagnostic = variant['diagnostic']
                assert project(public, public['files'], obs, diagnostic) == variant['request']
                executions += diagnostic['additional_executions']
                available += diagnostic['available']
                for item in diagnostic['records']:
                    if item['available']:
                        trace = item['trace_result']['trace']
                        assert expand_trace(compact_trace(trace)) == trace
        assert executions == 48 and available == 16
