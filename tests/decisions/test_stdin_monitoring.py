"""Presence-only monitoring preserves outcomes without counting every loop visit."""
import sys

import pytest

from vao.repair import stdin_ablation as ablation
from vao.repair.stdin_monitoring import MonitoringStdinVerifier, valid_monitoring_coverage
from vao.repair.stdin_verifier import StdinVerifier, compare_stdout

NATIVE = pytest.mark.skipif(sys.platform != 'darwin' or not hasattr(sys,'monitoring'),
                          reason='Native monitoring requires macOS and CPython >=3.12')


def test_monitoring_schema_is_explicit_and_distinct_from_trace_schema():
    data = {'version':'stdin-monitoring-line-coverage-v1','lines':[['main.py',1]],'line_events':1,
            'limit_reached':False,'intact':True,'event_limit':100000,'line_limit':4096}
    assert valid_monitoring_coverage(data,'print(1)\n')
    data['version']='stdin-main-line-coverage-v1'
    assert not valid_monitoring_coverage(data,'print(1)\n')


@NATIVE
def test_native_large_loop_presence_matches_short_loop_without_event_overflow():
    code=b'n=int(input())\ns=0\nfor i in range(n):\n    s+=i\nprint(s)\n'
    old=StdinVerifier();v=MonitoringStdinVerifier()
    short=old.invoke(code,b'3\n',coverage=True)
    large=old.invoke(code,b'300000\n',coverage=True)
    monitored=v.invoke(code,b'300000\n',coverage=True)
    assert short['coverage']['available'] and not large['coverage']['available']
    assert monitored['coverage']['available']
    assert short['coverage']['data']['lines']==monitored['coverage']['data']['lines']
    assert monitored['coverage']['data']['line_events']<20
    assert compare_stdout(monitored['observed'],str(sum(range(300000))).encode(),mode='ascii_whitespace_tokens')
    assert monitored['observed']==large['observed']


@NATIVE
def test_native_monitoring_isolation_and_exception_agreement():
    v=MonitoringStdinVerifier();assert v.preflight()['source_writes_denied']
    p={'schema_version':3,'instruction':'Print an integer.', 'files':{'main.py':'raise ValueError("bad")\n'},
       'comparator':'ascii_whitespace_tokens','public_cases':[{'id':'case_001','stdin':'','expected_stdout':'1\n'}]}
    stored=ablation.observe(p,v);acq=ablation.acquire(p,stored,v)
    assert ablation.analyze(p,stored,acq)['available']


@NATIVE
def test_native_disabling_monitoring_does_not_produce_valid_diagnostic():
    v=MonitoringStdinVerifier()
    code=b'import sys\nsys.monitoring.set_events(sys.monitoring.COVERAGE_ID,0)\nprint(1)\n'
    result=v.invoke(code,b'',coverage=True)
    assert compare_stdout(result['observed'],b'1\n',mode='exact_bytes')
    assert not result['coverage']['available']


@NATIVE
def test_native_nested_calls_generators_and_branches_match_reference_trace():
    code=b'''def values(n):
    for i in range(n):
        if i%2:
            yield i*2
        else:
            yield i
print(sum(values(int(input()))))
'''
    old=StdinVerifier().invoke(code,b'10\n',coverage=True)
    new=MonitoringStdinVerifier().invoke(code,b'10\n',coverage=True)
    assert old['coverage']['available'] and new['coverage']['available']
    assert old['observed']==new['observed']
    assert old['coverage']['data']['lines']==new['coverage']['data']['lines']
