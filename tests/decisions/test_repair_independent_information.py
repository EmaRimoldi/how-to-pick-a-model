"""Independent fresh cells, durable uncertainty, no outcomes in dispatch rules."""
import copy
import io
import json
from decimal import Decimal
from email.message import Message
import urllib.error

import pytest

from test_repair_qwen_information_study import Verifier, records, FIXED, BROKEN
from vao.repair import contract_collection as cc, independent_information_study as ds, streaming
from vao.repair.contracts import INDEPENDENT_TRACE_STUDY, STREAM_TRACE_STUDY
from vao.repair.environment import canonical, identity
from vao.repair.provider import OpenRouterTransport, ProviderStopped
from vao.repair.records import rows
from vao.analysis.repair_information import summarize


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'source_commit', lambda: 'a'*40)
    monkeypatch.setattr(cc, 'RepairVerifier', Verifier)
    monkeypatch.setattr(ds, 'validate_origin', lambda p: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'mock-key-only')
    now=[1000.0]
    def sleep(seconds): now[0]+=seconds
    monkeypatch.setattr('vao.repair.provider.time.sleep', sleep)
    monkeypatch.setattr('vao.repair.provider.time.monotonic', lambda: now[0])
    prior=tmp_path/'prior.json'
    prior.write_text(json.dumps({'study':STREAM_TRACE_STUDY,'model_results':True,
        'status':'incomplete_development_information_probe','gate':'inconclusive_incomplete_bank',
        'fit_selector':False,'accounting':{'cumulative_committed_usd':'0.12585127'}}))
    config={'status':'authorized_contract_diagnostic','study':INDEPENDENT_TRACE_STUDY,'live_calls_enabled':True,
        'authorization_reference':'MOCK TRANSPORT ONLY','monetary_authorization_usd':'0.47','cumulative_limit_usd':'0.60',
        'minimum_request_interval_seconds':60,'closed_pilot_report':str(prior)}
    p=ds.construct(records(),Verifier())
    return p,cc.freeze(p,config,tmp_path/'freeze.json')


def network(monkeypatch, packet, *, failures=None, useful=False, content_for=None):
    failures=failures or {};sent=[]
    lookup={canonical(r['provider_body']):r['metadata'] for r in packet['requests']}
    def preflight(self, endpoint, body=None):
        assert body is None
        if endpoint.endswith('/endpoints'):
            return {'data':{'id':self.settings.model,'endpoints':[{'tag':self.settings.endpoint,
                'provider_name':self.settings.provider_name,'quantization':self.settings.quantization,
                'context_length':131072,'max_completion_tokens':8192,
                'supported_parameters':['seed','temperature','max_tokens','response_format'],
                'pricing':{'prompt':'.00000012','completion':'.00000080'}}]}}
        if endpoint=='/key':return {'data':{'limit_remaining':1}}
        if endpoint=='/credits':return {'data':{'total_credits':1,'total_usage':0}}
        raise AssertionError('Nonstreaming POST')
    class Response:
        def __init__(self,data,failure):
            self.data=io.BytesIO(data);self.failure=failure;self.headers=Message();self.headers['Content-Type']='text/event-stream'
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read1(self,size):
            chunk=self.data.read(size)
            if chunk:return chunk
            if self.failure=='timeout':raise TimeoutError('mock-key-only')
            if self.failure=='reset':raise ConnectionResetError('mock-key-only')
            return b''
    class Opener:
        def open(self,request,timeout):
            body=json.loads(request.data);assert body['stream'] and timeout==180
            assert 'HIDDEN_CANARY' not in canonical(body)
            sent.append(body);failure=failures.get(len(sent));meta=lookup[canonical(body)]
            if failure=='headers':raise TimeoutError('mock-key-only')
            if failure=='http':raise urllib.error.HTTPError(request.full_url,429,'mock',{},io.BytesIO(b'{}'))
            code = content_for(meta) if content_for else (FIXED if useful and meta['arm']=='focused_trace' and meta['task_index']<3 else BROKEN)
            content=canonical({'solution.py': code})
            message={'id':f'mock-{len(sent)}','model':'qwen/qwen3-coder-next','provider':'Parasail',
                'choices':[{'index':0,'delta':{'content':content},'finish_reason':'stop'}]}
            if failure=='identity':message['provider']='Other'
            if failure in ('timeout','reset','eof'):message['choices'][0]['finish_reason']=None
            data='data: '+json.dumps(message)+'\n\n'
            if failure not in ('timeout','reset','eof','identity'):
                usage={'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,'cost':.02 if failure=='usage' else .00008}
                data+='data: '+json.dumps({**message,'choices':[],'usage':usage})+'\n\n'
            if not failure:data+='data: [DONE]\n\n'
            return Response(data.encode(),failure)
    monkeypatch.setattr(OpenRouterTransport,'_exchange',preflight)
    monkeypatch.setattr(streaming.urllib.request,'build_opener',lambda *_:Opener())
    return sent


def run(tmp_path,monkeypatch,*,failures=None,useful=False,stops=False):
    packet,frozen=prepare(tmp_path,monkeypatch)
    sent=network(monkeypatch,packet,failures=failures,useful=useful)
    output=tmp_path/'run'
    if stops:
        with pytest.raises(ProviderStopped):cc.collect(frozen,output,claim_root=tmp_path/'claims')
    else:cc.collect(frozen,output,claim_root=tmp_path/'claims')
    assert len(sent)==len({canonical(b) for b in sent})
    return packet,frozen,sent,output,summarize(output)


@pytest.mark.parametrize('useful,gate',[(True,'candidate_for_independent_acquisition_calibration'),
                                      (False,'no_completion_meets_development_screen')])
def test_complete_and_one_missing_banks_use_frozen_worst_case_screen(tmp_path,monkeypatch,useful,gate):
    packet,frozen,sent,output,report=run(tmp_path,monkeypatch,failures={2:'timeout'},useful=useful)
    assert len(sent)==64 and report['gate']==gate and not report['fit_selector']
    assert not report['accounting']['sealed'] and (output/'interruption.json').exists()
    assert sum(a['missing'] for a in report['arm_table'])==1
    assert report['contrasts']['focused_trace_minus_focused']['mean_difference'] is None
    assert report['contrasts']['focused_trace_minus_focused']['descriptive_bug_bootstrap_95'] is None
    assert Decimal(report['accounting']['cumulative_committed_usd'])==Decimal('.12585127')+63*Decimal('.00008')+Decimal('.00720896')
    events=[r for r in rows(output/'ledger.jsonl') if r['event']=='retain_unknown']
    assert len(events)==1 and events[0]['cooldown_elapsed_seconds']==120
    with pytest.raises(FileExistsError):cc.collect(frozen,tmp_path/'duplicate',claim_root=tmp_path/'claims')
    assert len(sent)==64


@pytest.mark.parametrize('useful',[False,True])
def test_complete_bank_mean_and_screen_agree(tmp_path,monkeypatch,useful):
    p,f,sent,out,r=run(tmp_path,monkeypatch,useful=useful)
    assert len(sent)==64 and r['accounting']['sealed']
    assert r['missingness_screen']['missing']==0
    assert r['missingness_screen']['mean']==r['contrasts']['focused_trace_minus_focused']['mean_difference']
    assert r['missingness_screen']['all_completions_pass']==useful


def test_third_consecutive_network_error_stops_without_another_admission(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={1:'timeout',2:'headers',3:'reset'},stops=True)
    assert len(sent)==3 and len(r['accounting']['pending'])==3
    assert sum(x['event']=='retain_unknown' for x in rows(out/'ledger.jsonl'))==2
    assert r['gate']=='inconclusive_selected_cell_bounds'
    assert sum(a['missing'] for a in r['arm_table'])==64


def test_any_valid_receipt_resets_only_the_network_error_streak(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={1:'timeout',2:'reset',4:'timeout',5:'reset'})
    assert len(sent)==64 and len(r['accounting']['pending'])==4
    assert all(a['successes']==0 for a in r['arm_table'])
    assert sum(x['event']=='retain_unknown' for x in rows(out/'ledger.jsonl'))==4


def test_eighth_total_network_error_stops_even_with_intervening_receipts(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={i:'timeout' for i in range(1,16,2)},stops=True)
    assert len(sent)==15 and len(r['accounting']['pending'])==8
    assert sum(x['event']=='retain_unknown' for x in rows(out/'ledger.jsonl'))==7


@pytest.mark.parametrize('failure',['http','identity','eof','usage'])
def test_http_identity_parser_and_partial_accounting_errors_are_terminal(tmp_path,monkeypatch,failure):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={1:failure},stops=True)
    assert len(sent)==1 and not any(x['event']=='retain_unknown' for x in rows(out/'ledger.jsonl'))
    committed=Decimal('.02') if failure=='usage' else Decimal('.00720896')
    assert Decimal(r['accounting']['study_committed_usd'])==committed
    assert r['gate']=='inconclusive_selected_cell_bounds'
    assert 'mock-key-only' not in ''.join(p.read_text() for p in out.rglob('*.json*'))


def test_changed_retention_receipt_or_cooldown_fails_independent_audit(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={2:'timeout'})
    ledger=rows(out/'ledger.jsonl');idx=next(i for i,e in enumerate(ledger) if e['event']=='retain_unknown')
    for changes in ({'cooldown_elapsed_seconds':0},{'metric_sha256':'0'*64},{'error_sha256':'0'*64}):
        changed=copy.deepcopy(ledger);changed[idx].update(changes)
        (out/'ledger.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in changed))
        with pytest.raises(ValueError):summarize(out)


def test_new_pairs_public_only_fixed_settings_and_history_disjoint():
    p=ds.construct(records(),Verifier());changed=records()
    for r in changed:r['evaluator']['cases'][0]['expected']=-55;r['source_full_pass']=not r['source_full_pass']
    q=ds.construct(changed,Verifier())
    assert [r['provider_body'] for r in p['requests']]==[r['provider_body'] for r in q['requests']]
    assert p['maximum_cumulative_commitment_usd']=='0.58722471'
    for a,b in zip(p['requests'][::2],p['requests'][1::2]):
        pair={r['metadata']['arm']:copy.deepcopy(r['provider_body']) for r in (a,b)}
        x,y=pair['focused'],pair['focused_trace'];px,py=[json.loads(z['messages'][1]['content']) for z in (x,y)]
        assert py.pop('runtime_diagnostic') and px==py
        y['messages']=x['messages'];assert x==y
    review=ds.validate_origin({'tasks':ds.source_records(),'requests':p['requests']})
    assert review['historical_archives']==14 and review['historical_unique_bodies']==556
    bad=copy.deepcopy(p);bad['design']['transport_missing_policy']['cooldown_seconds']=0
    bad['packet_id']=identity({k:v for k,v in bad.items() if k!='packet_id'})
    with pytest.raises(ValueError):ds.validate_packet(bad)


def test_no_report_before_terminal_record(tmp_path,monkeypatch):
    p,f,sent,out,r=run(tmp_path,monkeypatch,failures={1:'http'},stops=True)
    (out/'interruption.json').unlink()
    with pytest.raises(ValueError,match='before collection terminates'):summarize(out)


def test_independent_archive_replays_missingness_screen_and_saved_evaluations(tmp_path,monkeypatch):
    import hashlib
    import zipfile
    from vao.analysis import contract_verification as cv
    from vao.analysis.repair_information import render
    p,f,sent,out,report=run(tmp_path,monkeypatch,failures={2:'timeout'},useful=True)
    source=tmp_path/'export';source.mkdir()
    (source/'analysis.json').write_text(json.dumps(report))
    (source/'REPORT.md').write_text(render(report))
    members={}
    with zipfile.ZipFile(source/'evidence.zip','w') as z:
        for path in out.rglob('*'):
            if path.is_file():
                name='collection/'+path.relative_to(out).as_posix();data=path.read_bytes()
                z.writestr(name,data);members[name]=hashlib.sha256(data).hexdigest()
    (source/'evidence-manifest.json').write_text(json.dumps({'files':members,
        'archive_sha256':hashlib.sha256((source/'evidence.zip').read_bytes()).hexdigest()}))
    monkeypatch.setattr(cv,'RepairVerifier',Verifier)
    result=tmp_path/'reverified.json';cv.reproduce(source,result)
    checked=json.loads(result.read_text())
    assert checked['full_analysis_and_markdown_reproduced'] and checked['public_diagnostic_projections_reexecuted']
    assert checked['checked_evaluation_records']==126 and checked['discrepancies']==[]
