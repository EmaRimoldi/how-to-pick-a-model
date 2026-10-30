import copy
import json
from decimal import Decimal

import pytest

from vao.repair import spectrum_study as study
from vao.repair.provider import ProviderStopped


@pytest.fixture(scope='module')
def plan():
    return study.build_plan()


def test_real_projections_exclude_private_oracle_and_preserve_shared_core(plan):
    for r in plan['records']:
        f=study.project(r,'feedback');s=study.project(r,'spectrum')
        feedback=json.loads(f['messages'][1]['content'])
        diagnostic=json.loads(s['messages'][1]['content'])
        assert f['messages'][0]==s['messages'][0]
        del diagnostic['public_coverage']
        assert feedback==diagnostic
        altered=copy.deepcopy(r)
        altered['evaluator']={'cases':'PRIVATE_SENTINEL'}
        altered['source_full_pass']='ORACLE_SENTINEL'
        altered['public']['provenance']={'kind':'FIXED_SOURCE_SENTINEL'}
        altered['diagnostic']={'oracle':'ORACLE_LOCATION'}
        assert study.project(altered,'feedback')==f
        assert study.project(altered,'spectrum')==s


def test_full_ties_zero_scores_and_all_candidates_retained(plan):
    assert len(plan['candidate_inventory'])==12
    assert sum(r['public_passed'] for r in plan['candidate_inventory'])==4
    assert tuple(r['id'] for r in plan['records'])==study.IDS
    for r in plan['records']:
        d=json.loads(study.project(r,'spectrum')['messages'][1]['content'])['public_coverage']
        assert len(d['ranking'])==len(r['diagnostic']['ranking'])
        assert sum(len(g['locations']) for g in d['ranking'])==r['diagnostic']['metrics']['covered_lines']
        assert all(len(g['locations'])==g['rank_max']-g['rank_min']+1 for g in d['ranking'])
    tied=next(r for r in plan['records'] if r['id']=='youtube-dl-020')
    assert len(json.loads(study.project(tied,'spectrum')['messages'][1]['content'])['public_coverage']['ranking'][0]['locations'])==7


def test_unavailable_spectrum_does_not_drop_checkpoint(plan):
    r=copy.deepcopy(plan['records'][0])
    r['acquisition']['cases'][0]['ordinary']={'status':'timeout'}
    projected=json.loads(study.project(r,'spectrum')['messages'][1]['content'])
    assert projected['public_coverage']['available'] is False
    assert projected['public_coverage']['ranking'] is None
    assert projected['latest_feedback']==r['stored']['feedback']
    assert len(study.planned([r]))==6


def test_matched_seed_order_and_budget(plan):
    requests=plan['requests']
    assert len(requests)==48
    seeds={}
    for first,second in zip(requests[::2],requests[1::2]):
        a,b=first['metadata'],second['metadata']
        assert (a['task_index'],a['draw'])==(b['task_index'],b['draw'])
        assert a['arm']!=b['arm']
        assert first['provider_body']['seed']==second['provider_body']['seed']
        seeds[a['task_index'],a['draw']]=first['provider_body']['seed']
    assert len(set(seeds.values()))==24
    assert study.SETTINGS.reserve*48==Decimal('.34603008')
    assert study.CARRY+study.CAP==Decimal('.58775259')
    assert study.no_overlap(plan)['overlap']==0


def test_mutated_private_source_or_projection_rejected(plan):
    for path in ['requests','records']:
        corrupt=copy.deepcopy(plan)
        if path=='requests':
            corrupt['requests'][0]['provider_body']['messages'][1]['content']='different prompt'
        else:
            corrupt['records'][0]['evaluator']['cases'][0]['expected']='tampered oracle'
        corrupt['plan_id']=study.identity({k:v for k,v in corrupt.items() if k!='plan_id'})
        with pytest.raises(ValueError,match='changed'):
            study.validate_plan(corrupt)


def outcome_grid():
    return {(i,d,a):False for i in range(8) for d in range(3) for a in study.ARMS}


def test_gate_needs_repeatable_gain_and_cannot_discard_missingness():
    grid=outcome_grid()
    for i in range(3):
        for d in range(3):
            grid[i,d,'spectrum']=True
    good=study.summarize(grid)
    assert good['gate']=='passed_development_screen'
    assert good['difference_bounds_selected_counts']==[9,9]
    grid[7,2,'feedback']=None
    missing=study.summarize(grid)
    assert missing['gate']=='inconclusive_incomplete_bank'
    assert missing['difference_bounds_selected_counts']==[8,9]
    grid[7,2,'feedback']=False
    for i in range(3):
        grid[i,2,'feedback']=True
    assert study.summarize(grid)['gate']=='failed_development_screen'
    assert study.summarize(grid)['selector_training_allowed'] is False
    del grid[0,0,'feedback']
    with pytest.raises(ValueError,match='48'):
        study.summarize(grid)


def test_saved_verifier_scores_cannot_be_fabricated():
    cases=[{'id':'a','args':[],'expected':0}]
    result={'cases':[{'id':'a','passed':True,'observed':{'status':'returned','value':1}}],
            'passed':True,'passed_cases':1,'total_cases':1}
    with pytest.raises(ValueError,match='score'):
        study.check_saved_suite(result,cases)


def test_first_transport_failure_stops_and_cannot_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path)
    (tmp_path/'runs').mkdir()
    (tmp_path/'runs/ACTIVE_RESEARCH_STATE.json').write_text(json.dumps({'current_repair_budget':{
        'cumulative_committed_usd':str(study.CARRY),'total_unresolved_reservations':14,'active_collectors':0}}))
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-test-credential')
    monkeypatch.setattr(study,'validate_freeze',lambda *args,**kwargs:None)
    monkeypatch.setattr(study,'runtime',lambda:{})
    class Verifier:
        def preflight(self):return {'synthetic':True}
    class Transport:
        calls=0
        spent=Decimal(0)
        pending={'attempt':study.SETTINGS.reserve}
        conservative_committed_usd=study.SETTINGS.reserve
        def __init__(self,*args,**kwargs):pass
        def preflight(self):pass
        def complete(self,*args):
            Transport.calls+=1
            raise ProviderStopped('synthetic stop',http_status=429)
    monkeypatch.setattr(study,'RepairVerifier',Verifier)
    monkeypatch.setattr(study,'StreamingOpenRouterTransport',Transport)
    f={'freeze_id':'synthetic','runtime':{},'plan':{'records':[],'requests':[
        {'metadata':{'attempt_id':str(i)},'request':{}} for i in range(2)]}}
    out=tmp_path/'collection'
    assert study.collect(f,out)['status']=='interrupted'
    assert Transport.calls==1
    stopped=study.read(out/'interruption.json')
    assert Decimal(stopped['study_committed_usd'])==study.SETTINGS.reserve
    assert stopped['pending']=={'attempt':str(study.SETTINGS.reserve)}
    with pytest.raises(ValueError,match='resumed'):
        study.collect(f,out)
    with pytest.raises(FileExistsError):
        study.collect(f,tmp_path/'alternate-output')
    assert Transport.calls==1
