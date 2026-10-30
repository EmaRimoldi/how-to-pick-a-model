"""Information boundaries and exact controls in whole-program diagnostic inputs."""
import base64
from copy import deepcopy
import json
import sys

import pytest

from vao.repair import stdin_ablation as ablation
from vao.repair.environment import identity
from vao.repair.stdin_verifier import StdinVerifier

NATIVE = pytest.mark.skipif(sys.platform != 'darwin', reason='Native stdin backend needs macOS')


def public():
    return {'schema_version': 3, 'instruction': 'Print max(n,0), as an integer.',
            'files': {'main.py': 'n=int(input())\nif n > 0:\n    print(n-1)\nelse:\n    print(0)\n'},
            'comparator': 'ascii_whitespace_tokens',
            'public_cases': [{'id': 'case_001', 'stdin': '2\n', 'expected_stdout': '2\n'},
                             {'id': 'case_002', 'stdin': '-1\n', 'expected_stdout': '0\n'}]}


def record(stdout, lines=None):
    result = {'observed': {'status': 'exited', 'returncode': 0,
                          'stdout_b64': base64.b64encode(stdout).decode(), 'stderr_b64': ''},
              'elapsed_seconds': 0.01, 'candidate_executions': 1, 'python': '3.13.12'}
    if lines is not None:
        result['coverage'] = {'available': True, 'data': {'version': 'stdin-main-line-coverage-v1',
            'lines': [['main.py', n] for n in lines], 'line_events': len(lines), 'limit_reached': False,
            'intact': True, 'event_limit': 100000, 'line_limit': 4096}}
    return result


def fixture():
    p = public()
    stored = {'binding': ablation.binding(p), 'cases': [
        {'id': 'case_001', 'execution': record(b'1\n')},
        {'id': 'case_002', 'execution': record(b'0\n')}], 'candidate_executions': 2, 'seconds': 1.0}
    acquired = {'binding': stored['binding'], 'stored_identity': identity(stored),
                'cases': [{'id': 'case_001', 'ordinary': record(b'1\n'), 'covered': record(b'1\n', [1,2,3])},
                          {'id': 'case_002', 'ordinary': record(b'0\n'), 'covered': record(b'0\n', [1,2,5])}],
                'candidate_executions': 4, 'seconds': 1.0}
    return p, stored, acquired


def test_exact_scores_neutral_erasure_and_shared_information():
    p, s, a = fixture(); requests = ablation.triplet(p, s, a)
    payloads = {k: json.loads(v['messages'][1]['content']) for k,v in requests.items()}
    assert all(r['provider_call_enabled'] is False for r in requests.values())
    n, scored = [payloads[k]['source_excerpts']['locations'] for k in ['neutral', 'scored']]
    assert [r['line'] for r in scored] == [1,2,3,5]
    assert [r['squared_ochiai'] for r in scored] == [[1,2], [1,2], [1,1], [0,1]]
    assert all(r[k] == 'not supplied' for r in n for k in ['failing_covered','passing_covered','squared_ochiai'])
    assert [r['source'] for r in n] == [r['source'] for r in scored]
    assert 'rank' not in str(payloads['neutral'])
    assert 'candidate_executions' not in str(requests) and 'elapsed_seconds' not in str(requests)
    for arm in ['neutral','scored']:
        assert {k:v for k,v in payloads[arm].items() if k != 'source_excerpts'} == payloads['feedback']


@pytest.mark.parametrize('target', ['top', 'case', 'observation', 'coverage'])
def test_private_fields_rejected_at_every_supported_schema_boundary(target):
    p, s, a = fixture()
    if target == 'top': p['evaluator_reference'] = 'PRIVATE_SECRET'
    if target == 'case': p['public_cases'][0]['private_cases'] = ['PRIVATE_SECRET']
    if target == 'observation': s['cases'][0]['execution']['observed']['metadata'] = 'PRIVATE_SECRET'
    if target == 'coverage': a['cases'][0]['covered']['coverage']['data']['reference'] = 'PRIVATE_SECRET'
    with pytest.raises(ValueError): ablation.triplet(p, s, a)


@pytest.mark.parametrize('tamper', ['source','instruction','comparator','case_order','stored_id','acquisition_order'])
def test_stale_or_reordered_state_rejected(tamper):
    p, s, a = fixture()
    if tamper == 'source': p['files']['main.py'] += '# changed\n'
    if tamper == 'instruction': p['instruction'] += ' changed'
    if tamper == 'comparator': p['comparator'] = 'exact_bytes'
    if tamper == 'case_order': p['public_cases'].reverse()
    if tamper == 'stored_id': a['stored_identity'] = 'wrong'
    if tamper == 'acquisition_order': a['cases'].reverse()
    with pytest.raises(ValueError): ablation.triplet(p, s, a)


@pytest.mark.parametrize('field,value', [('seconds',float('nan')),('seconds',0),('candidate_executions',0),('candidate_executions',True)])
def test_acquisition_costs_cannot_be_dropped_or_nonfinite(field,value):
    p,s,a = fixture(); a[field] = value
    with pytest.raises(ValueError): ablation.triplet(p,s,a)


def test_unavailable_and_mismatched_diagnostics_are_retained_without_neutral_leaks():
    for reason in ['missing','limited','changed_stdout','changed_stderr']:
        p,s,a = fixture()
        c = a['cases'][0]['covered']
        if reason == 'missing': c['coverage'] = {'available': False, 'data': None}
        if reason == 'limited': c['coverage']['data']['limit_reached'] = True; c['coverage']['available'] = False
        if reason == 'changed_stdout': c['observed']['stdout_b64'] = base64.b64encode(b'2\n').decode()
        if reason == 'changed_stderr': c['observed']['stderr_b64'] = base64.b64encode(b'warning').decode()
        diagnostic = ablation.analyze(p,s,a)
        assert not diagnostic['available'] and diagnostic['invalid_or_mismatched_cases'] == ['case_001']
        requests = ablation.triplet(p,s,a)
        assert requests['neutral'] == requests['scored']
        payload = json.loads(requests['neutral']['messages'][1]['content'])['source_excerpts']
        assert payload == {'available':False,'reason':'incomplete_or_inconsistent_coverage','locations':None}
        assert diagnostic['candidate_executions'] == 4


def test_flat_spectrum_is_valid_and_complete_success_cannot_trigger_recovery():
    p,s,a = fixture()
    for row in a['cases']: row['covered']['coverage']['data']['lines'] = [['main.py',1],['main.py',2]]
    d=ablation.analyze(p,s,a)
    assert d['available'] and d['metrics']['positive_distinct_scores'] == 1
    assert [r['squared_ochiai'] for r in d['locations']] == [[1,2],[1,2]]
    p['public_cases'][0]['expected_stdout']='1\n';s['binding']=ablation.binding(p)
    with pytest.raises(ValueError,match='public failure'): ablation.project(p,s,'feedback')


def test_feedback_truncation_is_explicit_and_sandbox_nonce_is_not_behavior():
    p,s,a=fixture()
    old=s['cases'][0]['execution']['observed'];old['stderr_b64']=base64.b64encode(b'File "/tmp/repair-stdin-OLD/source/main.py", line 2\nValueError: bad').decode()
    for record_ in [a['cases'][0]['ordinary'],a['cases'][0]['covered']]:
        record_['observed']['stderr_b64']=base64.b64encode(b'File "/tmp/repair-stdin-NEW/source/main.py", line 2\nValueError: bad').decode()
    a['stored_identity']=identity(s)
    assert ablation.analyze(p,s,a)['available']
    result=ablation.visible_output(b'x'*2048)
    assert result['truncated'] and result['original_bytes']==2048 and len(result['text'])==1024
    assert not ablation.visible_output(b'\xff')['utf8_valid']


@NATIVE
def test_native_public_only_observation_and_coverage_match_real_branching():
    p=public();v=StdinVerifier();s=ablation.observe(p,v);a=ablation.acquire(p,s,v)
    diagnostic=ablation.analyze(p,s,a)
    assert diagnostic['available']
    assert diagnostic['metrics']['positive_distinct_scores']==2
    assert s['candidate_executions']==2 and a['candidate_executions']==4
    assert len(ablation.triplet(p,s,a))==3


@NATIVE
def test_native_exception_tracebacks_agree_across_fresh_sandboxes():
    p=public();p['files']['main.py']='raise ValueError("bad")\n'
    v=StdinVerifier();s=ablation.observe(p,v);a=ablation.acquire(p,s,v)
    assert ablation.analyze(p,s,a)['available']
    assert all(not r['passed'] for r in ablation.current_feedback(p,s)['cases'])
