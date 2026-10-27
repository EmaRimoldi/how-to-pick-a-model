"""Snapshot reuse, matched prompts, terminal inference and conserved billing."""
import copy
from decimal import Decimal
import hashlib
import itertools
import json
import zipfile

import pytest

from test_repair_contrastive_study import Verifier as BaseVerifier, records as base_records, FIXED, BROKEN
from test_repair_independent_information import network
from vao.repair import contract_collection as cc, region_information_study as ds
from vao.repair.acquisition_snapshot import acquire_once, runtime
from vao.repair.diagnostics import observe
from vao.repair.contracts import SNAPSHOT_TRACE_STUDY, COVERAGE_PREFIX_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.region_trace_worker import Trace
from vao.repair.provider import ProviderStopped
from vao.analysis.repair_region_information import summarize, render, screen


class AcquisitionVerifier(BaseVerifier):
    def trace(self, files, entry, case):
        return {'available': True, 'reason': None, 'observed': self.invoke(files, entry, case),
                'trace': Trace(['solution.py']).export(True)}


class Verifier(BaseVerifier):
    def trace(self, *args):
        raise AssertionError('Frozen acquisitions must never be reexecuted')


def records(tmp_path):
    result=[]
    for slug,r in zip(ds.IDS,base_records()):
        p=r['public'];state=observe(p,p['files'],AcquisitionVerifier());out=tmp_path/slug
        snapshot=acquire_once(out,p,p['files'],state,AcquisitionVerifier())
        result.append({'id':slug,'public':p,'evaluator':r['evaluator'],'observation':state,
            'source_public_result':state['feedback'],'diagnostic':snapshot['diagnostic'],
            'acquisition_claim':json.loads((out/'claim.json').read_text()),'acquisition_snapshot':snapshot,
            'acquisition_runtime':runtime(),'preparation_resources':{},'source_prefix_usd':'0',
            'checkpoint_kind':ds.design()['checkpoint_kind']})
    return result


def prepare(tmp_path,monkeypatch):
    monkeypatch.setattr(cc,'source_commit',lambda:'a'*40)
    monkeypatch.setattr(cc,'RepairVerifier',Verifier)
    monkeypatch.setattr(ds,'validate_origin',lambda _:None)
    monkeypatch.setenv('OPENROUTER_API_KEY','mock-key-only')
    now=[1000.0]
    monkeypatch.setattr('vao.repair.provider.time.sleep',lambda seconds:now.__setitem__(0,now[0]+seconds))
    monkeypatch.setattr('vao.repair.provider.time.monotonic',lambda:now[0])
    prior=tmp_path/'prior.json'
    prior.write_text(json.dumps({'study':COVERAGE_PREFIX_STUDY,'model_results':True,
        'status':'complete_initial_calibration','gate':'insufficient_failure_coverage_headroom',
        'fit_selector':False,'accounting':{'sealed':True,'cap_exceeded':False,'cumulative_committed_usd':str(ds.CARRY)}}))
    config={'status':'authorized_contract_diagnostic','study':SNAPSHOT_TRACE_STUDY,'live_calls_enabled':True,
        'authorization_reference':'MOCK TRANSPORT ONLY','monetary_authorization_usd':'.38','cumulative_limit_usd':'.60',
        'minimum_request_interval_seconds':60,'closed_pilot_report':str(prior)}
    p=ds.construct(records(tmp_path/'snapshots'),Verifier())
    return p,cc.freeze(p,config,tmp_path/'freeze.json')


def run(tmp_path,monkeypatch,*,benefit=False,failures=None,stops=False):
    p,f=prepare(tmp_path,monkeypatch)
    sent=network(monkeypatch,p,failures=failures,
        content_for=lambda m:FIXED if benefit and m['arm']=='focused_trace' and m['task_index']<3 else BROKEN)
    out=tmp_path/'run'
    if stops:
        with pytest.raises(ProviderStopped):cc.collect(f,out,claim_root=tmp_path/'claims')
    else:cc.collect(f,out,claim_root=tmp_path/'claims')
    return p,f,sent,out,summarize(out)


def test_exact_pairing_private_answer_exclusion_and_unique_fresh_requests(tmp_path):
    r=records(tmp_path);p=ds.construct(r,Verifier())
    seeds=set();orders=[]
    for start in range(0,32,2):
        pair=p['requests'][start:start+2];orders.append(tuple(x['metadata']['arm'] for x in pair))
        assert len({x['provider_body']['seed'] for x in pair})==1
        seeds.add(pair[0]['provider_body']['seed'])
        bodies={x['metadata']['arm']:copy.deepcopy(x['provider_body']) for x in pair}
        left,right=[json.loads(bodies[a]['messages'][1]['content']) for a in ds.ARMS]
        assert right.pop('runtime_diagnostic')['available'] and left==right
        bodies['focused_trace']['messages']=bodies['focused']['messages']
        assert bodies['focused_trace']==bodies['focused']
    assert len(seeds)==16 and orders.count(ds.ARMS)==8 and orders.count(tuple(reversed(ds.ARMS)))==8
    assert len({identity(x['provider_body']) for x in p['requests']})==32
    assert Decimal(p['maximum_new_reservations_usd'])==Decimal('.3670016')
    assert Decimal(p['maximum_cumulative_commitment_usd'])==Decimal('.57637531')
    r[0]['evaluator']['cases'][0]['expected']=12345
    q=ds.construct(r,Verifier())
    assert [x['provider_body'] for x in p['requests']]==[x['provider_body'] for x in q['requests']]
    assert 'HIDDEN_CANARY' not in canonical([x['provider_body'] for x in p['requests']])


def test_published_originals_and_saved_prompt_identity():
    p=ds.construct(ds.source_records(),Verifier())
    origin=ds.validate_origin(p)
    assert origin['source_candidates_verified']==8 and origin['historical_unique_bodies']==698
    assert origin['historical_overlap']==0
    assert all(r['diagnostic']['available'] for r in p['tasks'])


@pytest.mark.parametrize('field,value',[('requests',[]),('maximum_calls',33),('closed_pilot_commitment_usd','0'),('design',{}),('source_archive_sha256','changed')])
def test_rehash_cannot_change_cohort_design_or_carry(tmp_path,field,value):
    p=ds.construct(records(tmp_path),Verifier());p[field]=value
    p['packet_id']=identity({k:v for k,v in p.items() if k!='packet_id'})
    with pytest.raises(ValueError):ds.validate_packet(p)


def test_changed_snapshot_cannot_be_admitted(tmp_path,monkeypatch):
    p,f=prepare(tmp_path,monkeypatch);sent=network(monkeypatch,p)
    f['packet']['tasks'][0]['acquisition_snapshot']['diagnostic']['diagnostic_seconds']+=1
    f['packet']['packet_id']=identity({k:v for k,v in f['packet'].items() if k!='packet_id'})
    f['freeze_id']=identity({k:v for k,v in f.items() if k!='freeze_id'})
    with pytest.raises(ValueError):cc.collect(f,tmp_path/'run',claim_root=tmp_path/'claims')
    assert not sent and not (tmp_path/'claims').exists()


@pytest.mark.parametrize('benefit',[False,True])
def test_complete_screen_costs_and_no_trace_reexecution(tmp_path,monkeypatch,benefit):
    p,f,sent,out,r=run(tmp_path,monkeypatch,benefit=benefit)
    assert len(sent)==32 and r['accounting']['sealed'] and len(r['task_table'])==8
    assert (r['gate']=='candidate_for_generated_failure_calibration')==benefit and not r['fit_selector']
    assert Decimal(r['accounting']['cumulative_committed_usd'])==ds.CARRY+32*Decimal('.00008')
    assert r['acquisition_resources']['actual_frozen_acquisitions']==8
    assert r['acquisition_resources']['actual_frozen_sandbox_executions']==16
    assert [a['diagnostic_executions_per_deployment_sum'] for a in r['arm_table']]==[0,32]
    assert all(Decimal(a['counterfactual_prefix_usd'])==0 for a in r['arm_table'])
    assert r['contrasts']['focused_trace_minus_focused']['mean_difference']==(.375 if benefit else 0)
    with pytest.raises(FileExistsError):cc.collect(f,tmp_path/'duplicate',claim_root=tmp_path/'claims')
    assert len(sent)==32


def test_incomplete_positive_screen_still_inconclusive_and_reserve_kept(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,benefit=True,failures={2:'timeout'})
    assert len(sent)==32 and r['gate']=='inconclusive_incomplete_bank'
    assert len(r['accounting']['pending'])==1
    assert Decimal(r['accounting']['cumulative_committed_usd'])==ds.CARRY+31*Decimal('.00008')+Decimal('.0114688')
    c=r['contrasts']['focused_trace_minus_focused']
    assert c['mean_difference'] is None and c['descriptive_bug_bootstrap_95'] is None
    from vao.repair.contract_progress import progress
    op=progress(out);assert op['admissions']==32 and op['observations']==31
    assert op['cumulative_commitment_usd']==r['accounting']['cumulative_committed_usd']
    assert 'gate' not in op and 'arm_table' not in op


@pytest.mark.parametrize('failures,count',[({1:'http'},1),({1:'timeout',2:'headers',3:'reset'},3)])
def test_terminal_failure_retains_every_selected_cell_and_forbids_interim_analysis(tmp_path,monkeypatch,failures,count):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures=failures,stops=True)
    assert len(sent)==count and sum(a['missing'] for a in r['arm_table'])==32
    assert r['gate']=='inconclusive_incomplete_bank' and len(r['accounting']['pending'])==count
    (out/'interruption.json').unlink()
    with pytest.raises(ValueError,match='before terminal'):summarize(out)


def test_caps_and_prior_are_verified(tmp_path,monkeypatch):
    p,f=prepare(tmp_path,monkeypatch)
    for change in ({'monetary_authorization_usd':'.36'},{'monetary_authorization_usd':'.39'},{'cumulative_limit_usd':'.58'}):
        with pytest.raises(ValueError):cc.authorization({**f['config'],**change},p,f['prior_report'])
    for change in ({'gate':'other'},{'accounting':{'sealed':True,'cap_exceeded':False,'cumulative_committed_usd':'0'}}):
        with pytest.raises(ValueError):cc.authorization(f['config'],p,{**f['prior_report'],**change})


def test_finite_screen_extremes_and_replication_requirement():
    cells={(b,d,a):a=='focused_trace' for b in range(4) for d in range(2) for a in ds.ARMS}
    missing=[(0,0,'focused'),(1,1,'focused_trace'),(2,0,'focused_trace')]
    for k in missing:cells[k]=None
    original=copy.deepcopy(cells);decisions=[]
    for values in itertools.product((False,True),repeat=3):
        c={**cells,**dict(zip(missing,values))}
        repeated=sum(all(c[b,d,'focused_trace'] for d in range(2)) for b in range(4))
        diff=[sum(int(c[b,d,'focused_trace'])-int(c[b,d,'focused']) for b in range(4)) for d in range(2)]
        decisions.append(repeated>=3 and sum(diff)>=4 and all(v>0 for v in diff))
    s=screen(cells,list(range(4)))
    assert s['all_completions_pass']==all(decisions) and s['no_completion_passes']==(not any(decisions)) and original==cells


def test_saved_analysis_and_all_model_evaluations_replay_without_trace_reacquisition(tmp_path,monkeypatch):
    from vao.analysis import contract_verification as cv
    p,f,sent,out,r=run(tmp_path,monkeypatch,benefit=True)
    target=tmp_path/'export';target.mkdir();(target/'analysis.json').write_text(json.dumps(r));(target/'REPORT.md').write_text(render(r))
    members={}
    with zipfile.ZipFile(target/'evidence.zip','w') as z:
        for path in out.rglob('*'):
            if path.is_file():
                name='collection/'+path.relative_to(out).as_posix();data=path.read_bytes();z.writestr(name,data);members[name]=hashlib.sha256(data).hexdigest()
    (target/'evidence-manifest.json').write_text(json.dumps({'files':members,'archive_sha256':hashlib.sha256((target/'evidence.zip').read_bytes()).hexdigest()}))
    monkeypatch.setattr(cv,'RepairVerifier',Verifier);cv.reproduce(target,tmp_path/'replayed.json')
    checked=json.loads((tmp_path/'replayed.json').read_text())
    assert checked['checked_evaluation_records']==64 and checked['discrepancies']==[]
    assert checked['stored_public_diagnostics_verified'] and not checked['public_diagnostics_reexecuted']
