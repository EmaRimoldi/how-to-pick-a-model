"""Separately funded, single-use SSE compatibility probe on synthetic payloads.

No benchmark/repair outcome is evaluated. No closed request is replayed.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path

from .environment import canonical, identity
from .pilot import source_commit
from .provider import ProviderStopped, dollars
from .records import rows, save
from .streaming import StreamingOpenRouterTransport, StreamingSettings

ROOT = Path(__file__).resolve().parents[3]
STUDY = 'repair-sse-compatibility-v1'
LIMIT = Decimal('.03')
CARRY = Decimal('.10576463')
PRIOR = Path('experiments/python-repair/checkpoint-environment/results/information-extension-stopped-20261026/analysis.json')
PROTOCOL = Path('experiments/python-repair/checkpoint-environment/SSE-COMPATIBILITY-PROTOCOL.md')
CONFIG = Path('experiments/python-repair/checkpoint-environment/SSE-COMPATIBILITY-AUTHORIZED.json')
WIRE_STUDY = 'repair-sse-wire-envelope-v1'
SETTINGS = StreamingSettings(model='qwen/qwen3-coder-next', endpoint='parasail/bf16',
    provider_name='Parasail', quantization='bf16', input_per_million='0.12',
    output_per_million='0.80', seed=43133)


def specification(study):
    if study == STUDY:
        return {'study':study,'limit':LIMIT,'carry':CARRY,'prior':PRIOR,'protocol':PROTOCOL,
                'config':CONFIG,'settings':SETTINGS,'count':3,'max_wire_bytes':1048576}
    if study == WIRE_STUDY:
        base=Path('experiments/python-repair/checkpoint-environment')
        return {'study':study,'limit':Decimal('.01'),'carry':Decimal('.11456635'),
                'prior':base/'results/sse-compatibility-20261026/analysis.json',
                'protocol':base/'SSE-WIRE-ENVELOPE-PROTOCOL.md','config':base/'SSE-WIRE-ENVELOPE-AUTHORIZED.json',
                'settings':StreamingSettings(**{**asdict(SETTINGS),'seed':43134}),
                'count':1,'max_wire_bytes':8388608}
    raise ValueError('Undeclared engineering study')


def wire_packet():
    spec=specification(WIRE_STUDY);settings=spec['settings']
    request={'mode':'model_pilot','provider_call_enabled':True,'messages':[
        {'role':'system','content':'Return only a JSON object. Enumerate every requested item literally; do not use ellipses, ranges, code, expressions, explanations, or abbreviations.'},
        {'role':'user','content':canonical({'study':WIRE_STUDY,'instruction':'Return an object with the single key sequence. Its value is the ordered array of every integer from 0 through 8191 inclusive. Write every integer separately. Begin the array immediately and continue in ascending order.'})}]}
    meta={'trajectory':WIRE_STUDY+'-fixture-0','phase':'branch','depth':1,'draw':0}
    body=settings.body(request,meta);meta['attempt_id']=identity({'study':WIRE_STUDY,'fixture':0,'body':body})
    return {'study':WIRE_STUDY,'provider_settings':asdict(settings),'max_wire_bytes':spec['max_wire_bytes'],
            'requests':[{'fixture':0,'request':request,'metadata':meta,'provider_body':body}],
            'maximum_reservations_usd':str(settings.reserve),'scientific_results':False}


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def packet(study=STUDY):
    if study == WIRE_STUDY:return wire_packet()
    if study != STUDY:raise ValueError('Undeclared engineering study')
    requests=[]
    for i,n in enumerate((1,24,64)):
        code='\n\n'.join(f'def clamp_{j:03d}(value, lower, upper):\n    """Convert to integer and clamp to the inclusive bounds."""\n    return int(value)' for j in range(n))+'\n'
        request={'mode':'model_pilot','provider_call_enabled':True,'messages':[
            {'role':'system','content':'Return a JSON object mapping the filename to its full replacement Python source. Include every supplied function, no Markdown or omitted code.'},
            {'role':'user','content':canonical({'study':STUDY,'synthetic_transport_fixture':i,
                'instruction':'In every function, first reject lower > upper with ValueError, then convert value using int and clamp it to [lower, upper]. Preserve all function names and signatures. Return the complete file.',
                'files':{'synthetic_clamps.py':code}})}]}
        meta={'trajectory':f'{STUDY}-fixture-{i}','phase':'branch','depth':1,'draw':0}
        body=SETTINGS.body(request,meta)
        meta['attempt_id']=identity({'study':STUDY,'fixture':i,'body':body})
        requests.append({'fixture':i,'function_count':n,'request':request,'metadata':meta,'provider_body':body})
    return {'study':STUDY,'provider_settings':asdict(SETTINGS),'requests':requests,
            'maximum_reservations_usd':str(SETTINGS.reserve*3),'scientific_results':False}


def validate(frozen,current=False):
    if frozen.get('freeze_id')!=identity({k:v for k,v in frozen.items() if k!='freeze_id'}):
        raise ValueError('Probe freeze identity changed')
    spec=specification(frozen.get('study'))
    if frozen.get('packet')!=packet(spec['study']):raise ValueError('Probe request schedule changed')
    config=frozen['config']
    if (config.get('study')!=spec['study'] or config.get('status')!='authorized_transport_compatibility'
            or config.get('live_calls_enabled') is not True or dollars(config['monetary_authorization_usd'])!=spec['limit']
            or dollars(config['cumulative_limit_usd'])!=Decimal('.60')
            or config.get('minimum_request_interval_seconds')!=60 or not config.get('authorization_reference')):
        raise ValueError('Missing separately declared probe allocation')
    if dollars(frozen['prior'].get('accounting',frozen['prior'])['cumulative_committed_usd'])!=spec['carry'] or spec['carry']+spec['limit']>Decimal('.60'):
        raise ValueError('Historical carry changed')
    if current:
        if source_commit()!=frozen['source_commit']:raise ValueError('Source changed after freeze')
        for path in (spec['prior'],spec['protocol'],spec['config']):
            if sha(ROOT/path)!=frozen['input_hashes'][str(path)]:raise ValueError('Frozen input changed')
        if read(ROOT/spec['prior'])!=frozen['prior'] or read(ROOT/spec['config'])!=config:raise ValueError('Input differs')


def freeze(output,study=STUDY):
    spec=specification(study)
    f={'study':study,'created_utc':datetime.now(timezone.utc).isoformat(),'source_commit':source_commit(),
       'packet':packet(study),'config':read(ROOT/spec['config']),'prior':read(ROOT/spec['prior']),
       'input_hashes':{str(p):sha(ROOT/p) for p in (spec['prior'],spec['protocol'],spec['config'])}}
    f['freeze_id']=identity(f);validate(f,current=True);save(output,f)
    return {'freeze_id':f['freeze_id'],'source_commit':f['source_commit'],'planned_requests':spec['count'],
            'new_limit_usd':str(spec['limit']),
            'cumulative_max_design_usd':str(spec['carry']+spec['settings'].reserve*spec['count'])}


def collect(frozen,output,claim_root=None):
    validate(frozen,current=True)
    spec=specification(frozen['study']);settings=spec['settings']
    key=os.environ.get('OPENROUTER_API_KEY')
    if not key:raise ValueError('Private process credential required')
    if output.exists():raise ValueError('Probe output cannot resume')
    claims=claim_root or ROOT/'runs'/'repair-transport-admissions'
    claims.mkdir(parents=True,exist_ok=True)
    save(claims/(spec['study']+'.json'),{'freeze_id':frozen['freeze_id'],'output':str(output.resolve()),'resume_allowed':False})
    output.mkdir(parents=True)
    for d in ['requests','receipts']:(output/d).mkdir()
    save(output/'manifest.json',{'freeze':frozen,'study':spec['study'],'scientific_results':False})
    t=StreamingOpenRouterTransport(output,key,settings,authorized_limit_usd=str(spec['limit']),
        minimum_interval_seconds=60,max_wire_bytes=spec['max_wire_bytes'])
    generation_ids=set()
    try:
        t.preflight()
        for planned in frozen['packet']['requests']:
            save(output/'requests'/(planned['metadata']['attempt_id']+'.json'),planned)
            r=t.complete(planned['request'],planned['metadata'])
            if r['generation_id'] in generation_ids:raise ProviderStopped('Duplicate generation identity')
            generation_ids.add(r['generation_id'])
        if source_commit()!=frozen['source_commit']:raise ValueError('Source changed while collecting')
    except Exception as exc:
        save(output/'interruption.json',{'exception_type':type(exc).__name__,'resume_allowed':False,
             'known_usd':str(t.spent),'pending':{k:str(v) for k,v in t.pending.items()},
             'study_committed_usd':str(t.conservative_committed_usd),
             'cumulative_committed_usd':str(spec['carry']+t.conservative_committed_usd)})
        raise
    save(output/'completion.json',{'received':len(generation_ids),'known_usd':str(t.spent),
         'cumulative_committed_usd':str(spec['carry']+t.conservative_committed_usd),'scientific_results':False})


def audit(output):
    manifest=read(output/'manifest.json')
    spec=specification(manifest.get('study'));settings=spec['settings'];count=spec['count']
    if manifest.get('scientific_results') is not False:raise ValueError('Probe manifest differs')
    f=manifest['freeze'];validate(f)
    if f['study']!=spec['study']:raise ValueError('Manifest/freeze study differs')
    schedule={r['metadata']['attempt_id']:r for r in f['packet']['requests']}
    pending={};settled={};order=[];spent=Decimal(0);seen_generations=set();received=[]
    for event in rows(output/'ledger.jsonl'):
        k=event['attempt_id'];amount=dollars(event['usd'])
        if event.get('currency')!='USD':raise ValueError('Ledger currency differs')
        if event['event']=='reserve':
            if k in pending or k in settled or k not in schedule or pending:raise ValueError('Admission order or identity differs')
            if k!=f['packet']['requests'][len(order)]['metadata']['attempt_id'] or amount!=settings.reserve:
                raise ValueError('Frozen admission differs')
            if spent+amount>spec['limit']:raise ValueError('Admission exceeded cap')
            if read(output/'requests'/(k+'.json'))!=schedule[k] or read(output/'requests'/(k+'.provider.json'))!=schedule[k]['provider_body']:
                raise ValueError('Actual provider body differs')
            pending[k]=amount;order.append(k)
        elif event['event']=='settle':
            if k not in pending:raise ValueError('Settlement without admission')
            raw=read(output/'receipts'/(k+'.raw.json'));receipt=read(output/'receipts'/(k+'.json'))
            metrics=read(output/'stream-metrics'/(k+'.json'))
            if (amount!=dollars(raw['usage']['cost']) or amount!=dollars(receipt['cost_usd']) or amount>pending[k]
                    or raw.get('model')!=settings.model or raw.get('provider')!=settings.provider_name
                    or not raw.get('reconstructed_from_sse') or not metrics.get('stream_complete')
                    or not metrics.get('done_received') or not metrics.get('usage_received')
                    or metrics.get('wire_limit_bytes',1048576)!=spec['max_wire_bytes']
                    or receipt.get('generation_id')!=raw.get('id') or raw.get('id') in seen_generations
                    or receipt.get('usage')!=raw.get('usage') or receipt.get('content')!=raw['choices'][0]['message']['content']
                    or receipt.get('finish_reason')!=raw['choices'][0]['finish_reason']
                    or receipt.get('attempt_id')!=k or receipt.get('model')!=settings.model
                    or receipt.get('provider')!=settings.provider_name):
                raise ValueError('Receipt or SSE evidence differs')
            for field,bound in [('prompt_tokens',settings.input_token_ceiling),('completion_tokens',settings.max_tokens)]:
                if type(raw['usage'][field]) is not int or not 0<=raw['usage'][field]<=bound:raise ValueError('Token bound differs')
            seen_generations.add(raw['id']);settled[k]=amount;spent+=amount;del pending[k]
            try:
                artifact=json.loads(receipt['content']);json_file=isinstance(artifact,dict) and set(artifact)=={'synthetic_clamps.py'} and isinstance(artifact['synthetic_clamps.py'],str)
            except (ValueError,TypeError):json_file=False
            received.append({'fixture':schedule[k]['fixture'],'finish_reason':receipt['finish_reason'],
                'content_characters':len(receipt['content'] or ''),'json_file_contract':json_file,
                'cost_usd':str(amount),'elapsed_seconds':receipt['elapsed_seconds'],
                'sse_chunks':metrics['parsed_chunks'],'wire_bytes':metrics['wire_bytes']})
            if spec['study']==WIRE_STUDY:
                received[-1].pop('json_file_contract')
                received[-1].update(completion_tokens=raw['usage']['completion_tokens'],
                    wire_limit_bytes=metrics['wire_limit_bytes'])
        else:raise ValueError('Undeclared ledger event')
    errors=rows(output/'provider-errors.jsonl')
    if any(p.name.split('.')[0] not in order for p in (output/'receipts').glob('*.json')):raise ValueError('Orphan receipt')
    if set(e['attempt_id'] for e in errors)!=set(pending) or len(errors)!=len(pending):raise ValueError('Uncertain error records differ')
    committed=spent
    for k,reserve in pending.items():
        m=output/'stream-metrics'/(k+'.json')
        observed=dollars(read(m).get('reported_cost_usd','0')) if m.exists() else Decimal(0)
        committed+=max(reserve,observed)
    complete=(output/'completion.json').exists()
    interrupted=(output/'interruption.json').exists()
    if complete and (interrupted or len(settled)!=count or pending):raise ValueError('Invalid completion')
    if not complete and not interrupted:raise ValueError('Terminal audit requires a closed probe')
    terminal=read(output/('completion.json' if complete else 'interruption.json'))
    if dollars(terminal['cumulative_committed_usd'])!=spec['carry']+committed:raise ValueError('Terminal commitment differs')
    result={'study':spec['study'],'status':'complete_compatibility_probe' if complete else 'incomplete_compatibility_probe',
        'planned':count,'admitted':len(order),'received':len(settled),'uncertain':len(pending),'never_admitted':count-len(order),
        'known_usd':str(spent),'study_committed_usd':str(committed),'cumulative_committed_usd':str(spec['carry']+committed),
        'cap_exceeded':committed>spec['limit'] or spec['carry']+committed>Decimal('.60'),'received_records':received,
        'gate':'compatibility_observed' if complete else 'inconclusive','scientific_results':False,
        'limitations':['Three synthetic fixtures cannot establish production reliability or repair efficacy.',
                       'No randomized non-streaming comparator; reset causation remains unestablished.',
                       'Historical uncertainties remain missing and reserved; no retries or resumption.']}

    if spec['study']==WIRE_STUDY:
        crossed=bool(complete and received[0]['wire_bytes']>1048576
                     and received[0]['completion_tokens']==settings.max_tokens
                     and received[0]['finish_reason']=='length')
        result['gate']='larger_wire_envelope_observed' if crossed else 'inconclusive'
        result['old_limit_crossed_with_complete_receipt']=crossed
        result['limitations']=['One new synthetic request; no repair score, causal transport comparison or reliability estimate.',
                              'The declared check requires crossing 1 MiB and reaching 4096 output tokens with a length terminal receipt.',
                              'The old three-fixture probe stays inconclusive; its unknown is never repeated or filled.']
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','live','audit'])
    p.add_argument('--study',choices=[STUDY,WIRE_STUDY],default=STUDY);p.add_argument('--input',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.action=='freeze':
        if a.output is None:p.error('freeze needs output')
        result=freeze(a.output,a.study)
    elif a.action=='live':
        if a.input is None or a.output is None:p.error('live needs input and fresh output')
        collect(read(a.input),a.output);result=audit(a.output)
    else:
        if a.input is None:p.error('audit needs input')
        result=audit(a.input)
        if a.output:save(a.output,result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
