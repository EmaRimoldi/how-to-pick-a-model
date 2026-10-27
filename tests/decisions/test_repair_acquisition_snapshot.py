"""One-time acquisition boundaries, stochastic values and resource provenance."""
import json
import sys

import pytest

from vao.repair.acquisition_snapshot import acquire_once, load, projected, runtime
from vao.repair.diagnostics import observe
from vao.repair.environment import identity
from vao.repair.region_trace_worker import Trace
from vao.repair.region_verifier import RegionRepairVerifier


def task():
    return {'schema_version': 1, 'task_id': 'engineering/acquisition', 'instruction': 'Return x.',
            'entrypoint': {'module': 'solution', 'function': 'solve'},
            'files': {'solution.py': 'def solve(x):\n    return x + 1\n'},
            'public_cases': [{'id': 'first', 'args': [2], 'expected': 2}],
            'provenance': {'kind': 'engineering', 'private_metadata': 'PRIVATE_SENTINEL'}}


class CountingVerifier:
    def __init__(self, *, available=True, actual=3):
        self.calls, self.available, self.actual = 0, available, actual
    def invoke(self, *args):
        self.calls += 1
        return {'status': 'returned', 'value': self.actual}
    def trace(self, *args):
        self.calls += 1
        tracer = Trace(['solution.py'])
        trace = tracer.export(self.available)
        return {'available': self.available, 'reason': None if self.available else 'tracing_disabled',
                'trace': trace, 'observed': {'status': 'returned', 'value': self.actual}}


def observation(p):
    from vao.repair.diagnostics import binding
    return {'binding': binding(p, p['files']), 'verifier_seconds': .1,
            'feedback': {'passed': False, 'passed_cases': 0, 'total_cases': 1,
                         'cases': [{'id': 'first', 'passed': False, 'observed': {'status': 'returned', 'value': 3}}]}}


def test_acquire_once_loads_exact_bytes_without_extra_execution(tmp_path):
    p = task(); state = observation(p); verifier = CountingVerifier(); out = tmp_path/'capture'
    saved = acquire_once(out, p, p['files'], state, verifier)
    assert verifier.calls == 2
    first = load(out, p, p['files'], state, expected_runtime=runtime())
    second = load(out, p, p['files'], state)
    assert first == second == saved and verifier.calls == 2
    with pytest.raises(FileExistsError): acquire_once(out, p, p['files'], state, verifier)
    assert verifier.calls == 2
    baseline = projected(out, p, p['files'], state, 'focused')
    traced = projected(out, p, p['files'], state, 'focused_trace')
    left, right = [json.loads(x['messages'][1]['content']) for x in (baseline, traced)]
    assert right.pop('runtime_diagnostic')['available'] and left == right
    assert not baseline['provider_call_enabled'] and not traced['provider_call_enabled']
    assert 'PRIVATE_SENTINEL' not in (out/'claim.json').read_text() + json.dumps(traced)
    assert saved['diagnostic']['additional_executions'] == 2


@pytest.mark.parametrize('available,actual', [(False, 3), (True, 4)])
def test_unavailable_or_mismatched_trace_is_retained_not_excluded(tmp_path, available, actual):
    p=task(); state=observation(p); v=CountingVerifier(available=available, actual=actual)
    acquire_once(tmp_path/'capture', p, p['files'], state, v)
    result=load(tmp_path/'capture', p, p['files'], state)
    assert not result['diagnostic']['available'] and v.calls == 2
    prompt=projected(tmp_path/'capture',p,p['files'],state,'focused_trace')
    assert json.loads(prompt['messages'][1]['content'])['runtime_diagnostic']['trace'] is None


def test_public_pass_is_retained_without_acquiring(tmp_path):
    p=task();state=observation(p);state['feedback'].update(passed=True, passed_cases=1)
    state['feedback']['cases'][0]['passed']=True
    v=CountingVerifier();saved=acquire_once(tmp_path/'capture',p,p['files'],state,v)
    assert v.calls == 0 and saved['diagnostic']['additional_executions'] == 0
    assert saved['diagnostic']['reason'] == 'no_public_failure'


def test_interruption_keeps_claim_and_prohibits_loading_or_resumption(tmp_path):
    class Broken(CountingVerifier):
        def trace(self,*args): raise RuntimeError('synthetic interruption')
    p=task();state=observation(p);out=tmp_path/'capture';v=Broken()
    with pytest.raises(RuntimeError): acquire_once(out,p,p['files'],state,v)
    assert (out/'claim.json').exists() and (out/'interruption.json').exists()
    with pytest.raises(ValueError,match='completion'): load(out,p,p['files'],state)
    with pytest.raises(FileExistsError): acquire_once(out,p,p['files'],state,v)


@pytest.mark.parametrize('change',['bytes','context','runtime','seal','cost'])
def test_modified_snapshot_context_or_resource_accounting_fails_closed(tmp_path,change):
    p=task();state=observation(p);out=tmp_path/'capture'
    saved=acquire_once(out,p,p['files'],state,CountingVerifier())
    if change=='bytes':
        saved['diagnostic']['diagnostic_seconds']+=1
        (out/'snapshot.json').write_text(json.dumps(saved))
    if change=='context': p['files']['solution.py']+='\n# changed\n'
    if change=='runtime':
        frozen=runtime();frozen[next(iter(frozen))]='0'*64
        with pytest.raises(ValueError,match='runtime'):load(out,p,p['files'],state,expected_runtime=frozen)
        return
    if change=='seal':(out/'completion.json').write_text('{}')
    if change=='cost':
        saved['diagnostic']['additional_executions']=0
        saved['snapshot_id']=identity({k:v for k,v in saved.items() if k!='snapshot_id'})
        (out/'snapshot.json').write_text(json.dumps(saved))
    with pytest.raises(ValueError):load(out,p,p['files'],state)


@pytest.mark.skipif(sys.platform!='darwin',reason='macOS sandbox integration')
def test_native_stochastic_trace_remains_immutable_across_repeated_loads(tmp_path):
    p=task();p['files']={'solution.py':'def solve(x):\n    runtime_hash = hash("diagnostic-state")\n    return x + 1\n'}
    verifier=RegionRepairVerifier();state=observe(p,p['files'],verifier)
    saved=acquire_once(tmp_path/'capture',p,p['files'],state,verifier)
    events=saved['diagnostic']['trace_result']['trace']['events']
    assert any('runtime_hash' in e['locals'] for e in events)
    assert all(load(tmp_path/'capture',p,p['files'],state)==saved for _ in range(3))
    assert projected(tmp_path/'capture',p,p['files'],state,'focused_trace') == projected(tmp_path/'capture',p,p['files'],state,'focused_trace')
