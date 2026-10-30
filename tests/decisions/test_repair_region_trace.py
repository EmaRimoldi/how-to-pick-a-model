"""Quality and boundary checks for the opt-in diagnostic, never repair efficacy."""
import ast
import copy
import inspect
import json
import sys
from types import SimpleNamespace

import pytest

from vao.repair import region_trace_worker as worker
from vao.repair import trace_worker as legacy
from vao.repair.environment import canonical
from vao.repair.region_verifier import RegionRepairVerifier
from vao.repair.verifier import RepairVerifier

ENTRY = {'module': 'solution', 'function': 'solve'}
NATIVE = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS sandbox integration')


def row(sequence, function='solve', line=1):
    return {'file': 'solution.py', 'function': function, 'function_line': line,
            'sequence': sequence, 'line': line, 'event': 'line', 'locals': {'x': sequence}}


def test_sampling_retains_early_regions_and_exact_values_in_chronological_order():
    events = [row(i, 'early' if i < 5 else 'later') for i in range(1, 201)]
    before = copy.deepcopy(events)
    selected, retention = worker.select_events(events)
    assert len(selected) == 32
    assert {r['function'] for r in selected} == {'early', 'later'}
    assert all(r['function'] == 'later' for r in events[-32:])
    assert [r['sequence'] for r in selected] == sorted({r['sequence'] for r in selected})
    assert all(r == events[r['sequence']-1] for r in selected)
    assert events == before and worker.select_events(events) == (selected, retention)
    assert retention['omitted_functions'] == 0


def test_function_definition_not_name_or_invocation_is_region():
    events = [row(i, 'method', 1 if i % 2 else 10) for i in range(1, 40)]
    selected, retention = worker.select_events(events)
    assert {e['function_line'] for e in selected} == {1, 10}
    assert retention['captured_functions'] == 2


def test_exception_initial_final_temporal_samples_are_distinct():
    events = [row(i) for i in range(1, 10)]
    events[2].update(event='exception', exception='ValueError')
    ordered = worker.priority_order(events)
    assert [r['sequence'] for r in ordered[:4]] == [9, 3, 1, 5]
    assert sorted(r['sequence'] for r in ordered) == list(range(1, 10))


def test_region_overflow_and_byte_omissions_are_explicit():
    events = [row(i, 'f'+str(i)) for i in range(1, 41)]
    selected, meta = worker.select_events(events)
    assert len(selected) == 32 and meta['omitted_functions'] == 8
    for r in events:
        r['locals'] = {'x': 'x'*4000}
    selected, meta = worker.select_events(events)
    assert len(selected) == 2 and meta['omitted_functions'] == 38
    assert meta['event_candidates_rejected_for_bytes'] == 38
    assert meta['selected_event_bytes'] <= 12000


def test_compaction_matches_legacy_without_arbitrary_object_access():
    assert ast.dump(ast.parse(inspect.getsource(worker.compact))) == ast.dump(ast.parse(inspect.getsource(legacy.compact)))
    class Hostile(list):
        def __repr__(self):
            pytest.fail('Candidate repr must not run')
        def __getitem__(self, key):
            pytest.fail('Candidate protocol must not run')
    recursive = []
    recursive.append(recursive)
    for obj in [Hostile(), recursive, float('nan'), 2**1000, {'x': list(range(9))}]:
        assert worker.compact(obj) == legacy.compact(obj)


def test_capture_and_buffer_ceilings_keep_omission_records(monkeypatch, tmp_path):
    file = str(tmp_path/'solution.py')
    frame = SimpleNamespace(f_code=SimpleNamespace(co_filename=file, co_name='solve', co_firstlineno=1),
                            f_lineno=2, f_locals={'x': 4})
    trace = worker.Trace([file])
    for _ in range(520):
        trace(frame, 'line', None)
    result = trace.export(True)
    assert result['events_captured'] == 512 and result['capture_limit_reached']
    assert result['events_dropped'] == 480 and result['events_seen'] == 520
    monkeypatch.setattr(worker, 'BUFFER_BYTES', 500)
    trace = worker.Trace([file])
    for _ in range(10):
        trace(frame, 'line', None)
    result = trace.export(True)
    assert result['buffer_limit_reached'] and result['buffer_event_bytes'] <= 500
    assert 0 < result['events_captured'] < 10


@pytest.mark.parametrize('change', ['count', 'sequence', 'bytes', 'functions', 'locals', 'limits', 'file', 'file_list', 'line'])
def test_parent_rejects_inconsistent_worker_metadata(monkeypatch, change):
    events = [row(1), row(2)]
    trace = worker.Trace(['solution.py'])
    trace.events, trace.seen = events, 2
    trace.buffer_bytes = sum(len(json.dumps(r).encode()) for r in events)
    result = {'observed': {'status': 'returned', 'value': 2}, 'trace': trace.export(True)}
    target = result['trace']
    if change == 'count': target['events_captured'] = 1
    if change == 'sequence': target['events'][1]['sequence'] = 1
    if change == 'bytes': target['retention']['selected_event_bytes'] = 0
    if change == 'functions': target['retention']['omitted_functions'] = 5
    if change == 'locals': target['events'][0]['locals'] = {str(i): i for i in range(9)}
    if change == 'limits': target['limits'] = []
    if change == 'file': target['events'][0]['file'] = 'private.py'
    if change == 'file_list': target['events'][0]['file'] = []
    if change == 'line': target['events'][0]['function_line'] = 0
    verifier = object.__new__(RegionRepairVerifier)
    monkeypatch.setattr(verifier, '_execute', lambda *a, **kw: result)
    response = verifier.trace({'solution.py': ''}, ENTRY, {'args': []})
    assert not response['available'] and response['reason'] == 'invalid_trace_bounds'


@NATIVE
def test_native_two_module_trace_preserves_result_and_early_values():
    files = {'solution.py': 'from helper import early, later\ndef solve(x):\n    y = early(x)\n    return later(y)\n',
             'helper.py': 'def early(x):\n    y = x + 1\n    return y\ndef later(y):\n    for i in range(50):\n        y += 1\n    return y\n'}
    case = {'args': [2], 'expected': 'PRIVATE_SENTINEL'}
    ordinary = RepairVerifier().invoke(files, ENTRY, case)
    old = RepairVerifier().trace(files, ENTRY, case)
    new = RegionRepairVerifier().trace(files, ENTRY, case)
    assert new['available'] and old['available']
    assert ordinary == old['observed'] == new['observed'] == {'status': 'returned', 'value': 53}
    assert not any(e['function'] == 'early' for e in old['trace']['events'])
    assert any(e['function'] == 'early' and e.get('returned') == 3 for e in new['trace']['events'])
    assert {e['file'] for e in new['trace']['events']} == set(files)
    assert 'PRIVATE_SENTINEL' not in canonical(new)


@NATIVE
@pytest.mark.parametrize('source,observed', [
    ('def solve(x):\n    raise ValueError("message")\n', {'status': 'exception', 'exception': 'ValueError'}),
    ('def solve(x):\n    return {1, 2}\n', {'status': 'non_json_output'}),
    ('def solve(:\n    pass\n', {'status': 'load_error', 'exception': 'SyntaxError'}),
])
def test_native_exceptions_and_invalid_outputs_match_ordinary(source, observed):
    files, case = {'solution.py': source}, {'args': [2]}
    new = RegionRepairVerifier().trace(files, ENTRY, case)
    assert new['available'] and new['observed'] == RepairVerifier().invoke(files, ENTRY, case) == observed


@NATIVE
def test_native_worker_does_not_receive_expected_answers_or_trust_disabled_trace():
    source = 'import inspect\ndef solve(x):\n    assert "expected" not in inspect.currentframe().f_back.f_locals["payload"]\n    return x\n'
    verifier = RegionRepairVerifier()
    new = verifier.trace({'solution.py': source}, ENTRY, {'args': [2], 'expected': 'PRIVATE_SENTINEL'})
    assert new['available'] and new['observed'] == {'status': 'returned', 'value': 2}
    assert 'PRIVATE_SENTINEL' not in canonical(new)
    source = 'import sys\ndef solve(x):\n    sys.settrace(None)\n    return x\n'
    new = verifier.trace({'solution.py': source}, ENTRY, {'args': [2]})
    assert not new['available'] and new['reason'] == 'tracing_disabled'


@NATIVE
def test_native_limits_and_timeout_are_reported():
    source = 'def solve(x):\n    for i in range(1000):\n        x += 1\n    return x\n'
    new = RegionRepairVerifier().trace({'solution.py': source}, ENTRY, {'args': [0]})
    assert new['available'] and new['observed'] == {'status': 'returned', 'value': 1000}
    assert new['trace']['events_captured'] == 512 and new['trace']['capture_limit_reached']
    source = 'def solve(x):\n    while True: pass\n'
    new = RegionRepairVerifier(timeout=.2).trace({'solution.py': source}, ENTRY, {'args': [0]})
    assert not new['available'] and new['worker_result']['status'] == 'timeout'
