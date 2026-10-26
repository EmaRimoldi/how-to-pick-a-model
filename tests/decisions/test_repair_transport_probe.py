"""Synthetic source-freeze/admission/terminal audit checks; no network."""
from copy import deepcopy
import json

import pytest

from vao.repair import transport_probe as probe
from vao.repair.environment import identity
from vao.repair.provider import ProviderStopped
from vao.repair.records import save


def prepare(tmp_path,monkeypatch):
    monkeypatch.setattr(probe,'source_commit',lambda:'offline-test-commit')
    freeze_path=tmp_path/'freeze.json'
    probe.freeze(freeze_path)
    return json.loads(freeze_path.read_text())


def network(monkeypatch,failure_at=None,overage=False):
    calls=[]
    def preflight(self):self.ready=True
    def exchange(self,endpoint,body=None):
        assert endpoint=='/chat/completions' and body['stream'] is True
        calls.append(body)
        attempt=self._stream_attempt
        if failure_at==len(calls):
            save(self.output/'stream-metrics'/(attempt+'.json'),{'stream_complete':False,'reported_cost_usd':'.2' if overage else '0'})
            if overage:self.observed_costs[attempt]=probe.dollars('.2')
            raise ProviderStopped('synthetic failure',transport_kind='ConnectionResetError',transport_phase='reading_stream')
        save(self.output/'stream-metrics'/(attempt+'.json'),{'stream_complete':True,'done_received':True,
            'usage_received':True,'parsed_chunks':8,'wire_bytes':1500,'reported_cost_usd':'.001'})
        return {'id':f'gen-synthetic-{len(calls)}','model':self.settings.model,'provider':self.settings.provider_name,
                'reconstructed_from_sse':True,'choices':[{'finish_reason':'stop','message':{'content':'{"synthetic_clamps.py":"pass"}'}}],
                'usage':{'cost':.001,'prompt_tokens':100,'completion_tokens':10,'total_tokens':110}}
    monkeypatch.setattr(probe.StreamingOpenRouterTransport,'preflight',preflight)
    monkeypatch.setattr(probe.StreamingOpenRouterTransport,'_exchange',exchange)
    monkeypatch.setattr('vao.repair.provider.time.sleep',lambda _:None)
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-key-never-a-live-credential')
    return calls


def test_three_distinct_synthetic_requests_and_bounded_reservations():
    p=probe.packet()
    assert [r['function_count'] for r in p['requests']]==[1,24,64]
    assert len({r['metadata']['attempt_id'] for r in p['requests']})==3
    assert p['maximum_reservations_usd']=='0.02162688'
    assert probe.CARRY+probe.SETTINGS.reserve*3==probe.dollars('.12739151')
    assert all(r['provider_body']['stream'] is True for r in p['requests'])


def test_completed_probe_audits_all_receipts_and_is_single_use(tmp_path,monkeypatch):
    f=prepare(tmp_path,monkeypatch);calls=network(monkeypatch)
    out=tmp_path/'run';claims=tmp_path/'claims'
    probe.collect(f,out,claims)
    a=probe.audit(out)
    assert a['received']==3 and a['known_usd']=='0.003' and a['cumulative_committed_usd']=='0.10876463'
    assert a['gate']=='compatibility_observed' and a['scientific_results'] is False
    assert len(calls)==3 and a['uncertain']==a['never_admitted']==0
    with pytest.raises(ValueError):probe.collect(f,out,claims)
    with pytest.raises(FileExistsError):probe.collect(f,tmp_path/'new-output',claims)
    assert len(calls)==3


@pytest.mark.parametrize('failure_at', [1,2,3])
def test_first_failure_stops_and_keeps_all_planned_fixtures(tmp_path,monkeypatch,failure_at):
    f=prepare(tmp_path,monkeypatch);calls=network(monkeypatch,failure_at)
    out=tmp_path/'run'
    with pytest.raises(ProviderStopped):probe.collect(f,out,tmp_path/'claims')
    a=probe.audit(out)
    assert a['received']==failure_at-1 and a['uncertain']==1 and a['never_admitted']==3-failure_at
    assert len(calls)==failure_at and a['gate']=='inconclusive'
    assert probe.dollars(a['study_committed_usd'])==probe.dollars('.001')*(failure_at-1)+probe.SETTINGS.reserve
    assert not (out/'completion.json').exists()


def test_unknown_overage_is_preserved_in_terminal_accounting(tmp_path,monkeypatch):
    f=prepare(tmp_path,monkeypatch);calls=network(monkeypatch,1,overage=True)
    out=tmp_path/'run'
    with pytest.raises(ProviderStopped):probe.collect(f,out,tmp_path/'claims')
    a=probe.audit(out)
    assert a['cap_exceeded'] and a['study_committed_usd']=='0.2'
    assert a['cumulative_committed_usd']=='0.30576463' and len(calls)==1


@pytest.mark.parametrize('damage',['body','cap','prior','source'])
def test_rehashed_freeze_drift_is_rejected_before_calls(tmp_path,monkeypatch,damage):
    f=prepare(tmp_path,monkeypatch);calls=network(monkeypatch)
    if damage=='body':f['packet']['requests'][0]['provider_body']['stream']=False
    if damage=='cap':f['config']['monetary_authorization_usd']='.04'
    if damage=='prior':f['prior']['accounting']['cumulative_committed_usd']='0'
    if damage=='source':f['source_commit']='other'
    f['freeze_id']=identity({k:v for k,v in f.items() if k!='freeze_id'})
    with pytest.raises(ValueError):probe.collect(f,tmp_path/'run',tmp_path/'claims')
    assert not calls and not (tmp_path/'claims').exists()


@pytest.mark.parametrize('damage',['provider_body','receipt_content','currency','settlement','orphan'])
def test_terminal_audit_rejects_changed_evidence(tmp_path,monkeypatch,damage):
    f=prepare(tmp_path,monkeypatch);network(monkeypatch)
    out=tmp_path/'run';probe.collect(f,out,tmp_path/'claims')
    key=f['packet']['requests'][0]['metadata']['attempt_id']
    if damage=='provider_body':
        path=out/'requests'/(key+'.provider.json');d=json.loads(path.read_text());d['stream']=False;path.write_text(json.dumps(d))
    elif damage=='receipt_content':
        path=out/'receipts'/(key+'.json');d=json.loads(path.read_text());d['content']='changed';path.write_text(json.dumps(d))
    elif damage=='orphan':save(out/'receipts/orphan.raw.json',{})
    else:
        path=out/'ledger.jsonl';d=[json.loads(l) for l in path.read_text().splitlines()]
        if damage=='currency':d[0]['currency']='other'
        else:d[1]['usd']='0'
        path.write_text('\n'.join(json.dumps(x) for x in d)+'\n')
    with pytest.raises(ValueError):probe.audit(out)
