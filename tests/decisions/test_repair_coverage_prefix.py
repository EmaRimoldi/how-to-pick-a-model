"""Natural failure admission, public-only gates, missingness and bounded costs."""
import copy
from decimal import Decimal
import hashlib
import json
import zipfile

import pytest

from test_repair_independent_information import network
from test_repair_contrastive_study import Verifier, records, FIXED, BROKEN
from vao.repair import contract_collection as cc, coverage_prefix as ds
from vao.repair.contracts import COVERAGE_PREFIX_STUDY, CONTRASTIVE_TRACE_STUDY
from vao.repair.environment import RepairTask, canonical, identity
from vao.repair.provider import ProviderStopped
from vao.analysis.repair_coverage_prefix import summarize, render


def tasks():
    result = []
    for r in records()[:6]:
        r['public']['public_cases'].append({'id': 'second-failure', 'args': [2], 'expected': 2})
        result.append(RepairTask.from_dicts(r['public'], r['evaluator']))
    return result


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a' * 40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setattr(ds, 'validate_origin', lambda _: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'mock-key-only')
    now = [1000.0]
    monkeypatch.setattr('vao.repair.provider.time.sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr('vao.repair.provider.time.monotonic', lambda: now[0])
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'study': CONTRASTIVE_TRACE_STUDY, 'model_results': True,
        'gate': 'no_completion_meets_development_screen', 'fit_selector': False,
        'accounting': {'sealed': True, 'cumulative_committed_usd': str(ds.CARRY)}}))
    config = {'status': 'authorized_contract_diagnostic', 'study': COVERAGE_PREFIX_STUDY,
        'live_calls_enabled': True, 'authorization_reference': 'MOCK TRANSPORT ONLY',
        'monetary_authorization_usd': '0.04', 'cumulative_limit_usd': '0.60',
        'minimum_request_interval_seconds': 60, 'closed_pilot_report': str(prior)}
    p = ds.construct(tasks(), Verifier())
    return p, cc.freeze(p, config, tmp_path / 'freeze.json')


def test_one_initial_draw_per_task_and_private_answers_never_enter_body():
    p = ds.construct(tasks(), Verifier())
    changed = []
    for t in tasks():
        ev = json.loads(t.evaluator_json); ev['cases'][0]['expected'] = 12345
        changed.append(RepairTask.from_dicts(t.public, ev))
    q = ds.construct(changed, Verifier())
    assert [r['provider_body'] for r in p['requests']] == [r['provider_body'] for r in q['requests']]
    assert len(p['requests']) == len({r['metadata']['task_index'] for r in p['requests']}) == 6
    assert len({r['provider_body']['seed'] for r in p['requests']}) == 6
    assert 'HIDDEN_CANARY' not in canonical([r['provider_body'] for r in p['requests']])
    assert Decimal(p['maximum_new_reservations_usd']) == Decimal('0.03809280')
    assert p['maximum_cumulative_commitment_usd'] == '0.24449551'
    assert all('runtime_diagnostic' not in json.loads(r['request']['messages'][1]['content']) for r in p['requests'])


@pytest.mark.parametrize('field,value', [('closed_pilot_commitment_usd','0'), ('maximum_calls',7),
    ('pool_sha256','wrong'), ('requests',[]), ('design',{})])
def test_rehash_does_not_allow_cohort_or_budget_changes(field, value):
    p = ds.construct(tasks(), Verifier()); p[field] = value
    p['packet_id'] = identity({k:v for k,v in p.items() if k != 'packet_id'})
    with pytest.raises(ValueError): ds.validate_packet(p)


@pytest.mark.parametrize('successful,eligible', [(0,6),(3,3),(4,2),(6,0)])
def test_difficulty_gate_does_not_reward_easy_tasks(tmp_path, monkeypatch, successful, eligible):
    p,f = prepare(tmp_path, monkeypatch)
    sent = network(monkeypatch,p,content_for=lambda m: FIXED if m['task_index'] < successful else BROKEN)
    out = tmp_path / 'run'; cc.collect(f,out,claim_root=tmp_path/'claims')
    r = summarize(out)
    assert len(sent) == 6 and r['full_successes'] == successful
    assert r['eligible_recovery_checkpoints'] == r['multiple_public_failure_checkpoints'] == eligible
    assert (r['gate'] == 'eligible_for_prespecified_recovery_stage') == (eligible >= 3)
    assert not r['fit_selector'] and not r['diagnostic_benefit_established']
    assert Decimal(r['accounting']['cumulative_committed_usd']) == ds.CARRY + Decimal('.00048')
    with pytest.raises(FileExistsError): cc.collect(f,tmp_path/'duplicate',claim_root=tmp_path/'claims')
    assert len(sent) == 6
    from vao.analysis.contract_diagnostic import summarize as old_report
    with pytest.raises(ValueError,match='coverage-prefix report'): old_report(out)


def test_first_uncertain_call_stops_without_successor_and_keeps_all_six(tmp_path, monkeypatch):
    p,f = prepare(tmp_path,monkeypatch)
    sent = network(monkeypatch,p,failures={2:'timeout'},content_for=lambda _:BROKEN)
    out = tmp_path/'run'
    with pytest.raises(ProviderStopped): cc.collect(f,out,claim_root=tmp_path/'claims')
    r = summarize(out)
    assert len(sent) == 2 and len(r['tasks']) == 6 and r['missing'] == 5
    assert r['gate'] == 'inconclusive_incomplete_prefix' and r['maximum_recovery_requests_if_permitted'] == 0
    assert Decimal(r['accounting']['cumulative_committed_usd']) == ds.CARRY + Decimal('.00008') + Decimal('.00634880')
    assert len(r['accounting']['pending']) == 1
    (out/'interruption.json').unlink()
    with pytest.raises(ValueError,match='terminal'): summarize(out)


def test_public_false_acceptance_never_triggers_recovery(tmp_path,monkeypatch):
    p,f = prepare(tmp_path,monkeypatch)
    wrong = 'def solve(x):\n    return x if x != 99 else 0\n'
    class Alternatives(Verifier):
        def invoke(self,files,entry,case):
            x=case['args'][0]
            if files['solution.py'] == wrong: return {'status':'returned','value':x if x != 99 else 0}
            return super().invoke(files,entry,case)
    monkeypatch.setattr(cc,'RepairVerifier',Alternatives)
    network(monkeypatch,p,content_for=lambda _:wrong)
    out=tmp_path/'run';cc.collect(f,out,claim_root=tmp_path/'claims')
    r=summarize(out)
    assert sum(c['false_public_acceptance'] for c in r['tasks']) == 6
    assert r['full_successes'] == r['eligible_recovery_checkpoints'] == 0
    assert r['gate'] == 'insufficient_failure_coverage_headroom'


def test_carry_and_caps_are_checked_before_admission(tmp_path,monkeypatch):
    p,f=prepare(tmp_path,monkeypatch)
    for change in ({'monetary_authorization_usd':'.03'}, {'monetary_authorization_usd':'.05'},
                   {'cumulative_limit_usd':'.24'}, {'live_calls_enabled':False}):
        with pytest.raises(ValueError):cc.authorization({**f['config'],**change},p,f['prior_report'])
    for change in ({'accounting':{'sealed':True,'cumulative_committed_usd':'0'}},
                   {'accounting':{'sealed':False,'cumulative_committed_usd':str(ds.CARRY)}}):
        with pytest.raises(ValueError):cc.authorization(f['config'],p,{**f['prior_report'],**change})


def test_evidence_replays_every_saved_evaluation(tmp_path,monkeypatch):
    from vao.analysis import contract_verification as cv
    p,f=prepare(tmp_path,monkeypatch)
    network(monkeypatch,p,content_for=lambda _:BROKEN)
    out=tmp_path/'run';cc.collect(f,out,claim_root=tmp_path/'claims')
    r=summarize(out);target=tmp_path/'export';target.mkdir()
    (target/'analysis.json').write_text(json.dumps(r));(target/'REPORT.md').write_text(render(r))
    members={}
    with zipfile.ZipFile(target/'evidence.zip','w') as z:
        for path in out.rglob('*'):
            if path.is_file():
                name='collection/'+path.relative_to(out).as_posix();data=path.read_bytes()
                z.writestr(name,data);members[name]=hashlib.sha256(data).hexdigest()
    (target/'evidence-manifest.json').write_text(json.dumps({'files':members,
        'archive_sha256':hashlib.sha256((target/'evidence.zip').read_bytes()).hexdigest()}))
    monkeypatch.setattr(cv,'RepairVerifier',Verifier)
    cv.reproduce(target,tmp_path/'replayed.json')
    replay=json.loads((tmp_path/'replayed.json').read_text())
    assert replay['checked_evaluation_records']==12 and not replay['discrepancies']
