"""Prospective public-spectrum development screen; explicit single-use collection."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import zipfile

from .contracts import decode, public_feedback
from .environment import REPAIR_SYSTEM, RepairTask, canonical, identity
from .independent_information_study import archived_requests
from .pilot import source_commit
from .provider import ProviderStopped, dollars
from .records import append, rows, save
from .region_information_study import HISTORY
from .spectra import analyze_spectrum, score
from .streaming import StreamingOpenRouterTransport, StreamingSettings
from .verifier import RepairVerifier

ROOT = Path(__file__).resolve().parents[3]
BASE = Path('experiments/python-repair/checkpoint-environment')
PROTOCOL = BASE / 'SPECTRUM-PROTOCOL.md'
CONFIG = BASE / 'SPECTRUM-AUTHORIZED.json'
AMENDMENT = BASE / 'SPECTRUM-IMPLEMENTATION-CORRECTION.md'
SPECTRA = BASE / 'results/generated-spectra-20261029/evidence.zip'
SPECTRA_SHA = '91ce9853e359486f7ba40b01e248fb3491d24337fd4c4ceba938e5927744e400'
SOURCE = BASE / 'results/contract-gemma27b-20261026/evidence.zip'
SOURCE_SHA = 'f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913'
STUDY = 'repair-public-spectrum-development-v1'
IDS = ('youtube-dl-003','youtube-dl-013','youtube-dl-020','youtube-dl-031',
       'youtube-dl-033','youtube-dl-042','youtube-dl-043','httpie-005')
ARMS = ('feedback','spectrum')
DRAWS, SEED = 3, 43141
CARRY, CAP = Decimal('.22775259'), Decimal('.36')
SETTINGS = StreamingSettings(model='qwen/qwen3-coder-next',endpoint='parasail/bf16',
    provider_name='Parasail',quantization='bf16',input_per_million='0.12',
    output_per_million='0.80',input_token_ceiling=32768,max_tokens=4096,seed=SEED)
SYSTEM = REPAIR_SYSTEM + (' If public coverage is supplied, it describes the current files. '
    'Squared Ochiai ranks association with failing tests, not fault probability. '
    'Tied lines are equally ranked; missing behavior may not execute at all. '
    'Preserve all required behavior, including cases that already pass.')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def archive(path, expected):
    if digest(path) != expected:
        raise ValueError('Frozen source archive changed')
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate source members')
        return {name:z.read(name) for name in z.namelist()}


def sources():
    """Public eligibility/ranking first; evaluator attached only for scoring."""
    data = archive(ROOT/SPECTRA,SPECTRA_SHA)
    manifest = json.loads(data['manifest.json'])
    if manifest != {k:hashlib.sha256(v).hexdigest() for k,v in data.items() if k!='manifest.json'}:
        raise ValueError('Spectrum evidence manifest differs')
    evidence = json.loads(data['evidence.json'])
    if evidence['bank'] != 'generated' or evidence['source_sha256'] != SOURCE_SHA:
        raise ValueError('Wrong diagnostic bank')
    records = evidence['records']
    inventory = evidence['candidate_inventory']
    if (tuple(r['id'] for r in records) != IDS or len(inventory)!=12
            or tuple(r['id'] for r in inventory if not r['public_passed']) != IDS):
        raise ValueError('Retain twelve candidates and all eight public failures')
    source = archive(ROOT/SOURCE,SOURCE_SHA)
    old = json.loads(source['collection/manifest.json'])['freeze']['packet']['tasks']
    attempts = {r['attempt_id']:r for r in
        [json.loads(line) for line in source['collection/observations.jsonl'].splitlines()]}
    prepared = []
    for r in records:
        observed = attempts[r['source_attempt_id']]
        original = old[observed['task_index']]
        obj = f"collection/cells/{r['source_attempt_id']}/objects/"
        files = json.loads(source[obj+observed['artifact']+'.json'])['files']
        feedback = public_feedback(json.loads(source[obj+observed['public']+'.json'])['result'])
        p = r['public']
        if (observed['contract']!='json_current' or files!=p['files']
                or feedback!=r['stored']['feedback'] or feedback['passed']
                or any(p[k]!=original['public'][k] for k in ('task_id','instruction','entrypoint','public_cases'))):
            raise ValueError('Generated checkpoint/public-only trigger differs')
        diagnostic = analyze_spectrum(p,r['acquisition'])
        prepared.append({**r,'diagnostic':diagnostic,'evaluator':original['evaluator'],
            'source_prefix_cost_usd':observed['cost_usd']})
    return inventory, prepared


def project(record, arm):
    """Explicit public allowlist; evaluator, historical correctness and IDs omitted."""
    if arm not in ARMS:
        raise ValueError('Unknown arm')
    p = record['public']
    core = {k:p[k] for k in ('instruction','entrypoint','public_cases','files')}
    core['latest_feedback'] = record['stored']['feedback']
    if arm == 'spectrum':
        diagnostic = analyze_spectrum(p,record['acquisition'])
        ranking = []
        if diagnostic['available']:
            for group in diagnostic['ranking']:
                ranking.append({k:group[k] for k in ('rank_min','rank_max','squared_exact')})
                ranking[-1]['locations'] = [{**loc,'source':p['files'][loc['file']].splitlines()[loc['line']-1]}
                                            for loc in group['locations']]
        core['public_coverage'] = {'available':diagnostic['available'],
            'invalid_cases':diagnostic['invalid_or_mismatched_cases'],
            'ranking':ranking if diagnostic['available'] else None,
            'meaning':'All observed lines; exact squared Ochiai ties retained; unexecuted code absent.'}
    return {'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':canonical(core)}],
            'mode':'model_pilot','provider_call_enabled':True}


def planned(records):
    blocks = [(i,d) for d in range(DRAWS) for i in range(len(records))]
    random.Random(SEED).shuffle(blocks)
    result = []
    for pos,(i,draw) in enumerate(blocks):
        for arm in (ARMS if pos%2==0 else tuple(reversed(ARMS))):
            r = records[i]
            meta = {'study':STUDY,'task_index':i,'task_id':r['id'],'draw':draw,'arm':arm,
                'trajectory':f'{STUDY}-{i}-draw-{draw}','phase':'branch','depth':1,
                'contract':'json_current','source_attempt_id':r['source_attempt_id']}
            meta['attempt_id'] = identity(meta)
            request = project(r,arm)
            result.append({'metadata':meta,'request':request,'provider_body':SETTINGS.body(request,meta)})
    return result


def build_plan():
    inventory, records = sources()
    plan = {'study':STUDY,'candidate_inventory':inventory,'records':records,'requests':planned(records),
        'provider_settings':asdict(SETTINGS),'draws':DRAWS,'arms':list(ARMS),
        'prior_committed_usd':str(CARRY),'cap_usd':str(CAP),
        'maximum_reservations_usd':str(SETTINGS.reserve*48),'historical_reserves':14,
        'spectrum_archive_sha256':SPECTRA_SHA,'source_archive_sha256':SOURCE_SHA}
    plan['plan_id'] = identity(plan)
    return plan


def validate_plan(plan):
    if plan != build_plan():
        raise ValueError('Selected inputs, projections, schedule or accounting changed')
    requests = plan['requests']
    if len(requests)!=48 or len({identity(r['provider_body']) for r in requests})!=48:
        raise ValueError('Expected 48 distinct requests')
    if SETTINGS.reserve*48>CAP or CARRY+CAP>Decimal('.60'):
        raise ValueError('Declared budget insufficient')


def no_overlap(plan):
    history = {**HISTORY,str(BASE/'results/frozen-region-stopped-20261027/evidence.zip'):
        'ab4f4f8e4d38a9bc8178477e695fd18e1854887c563fb349bfb6bd9e7ba20038'}
    old_ids, old_bodies = set(), set()
    for path,sha in history.items():
        data = archive(ROOT/path,sha)
        for name,raw in data.items():
            if name.startswith('collection/') and name.endswith('/manifest.json'):
                for r in archived_requests(json.loads(raw)):
                    old_ids.add(r['metadata']['attempt_id']);old_bodies.add(identity(r['provider_body']))
    if (old_ids & {r['metadata']['attempt_id'] for r in plan['requests']}
            or old_bodies & {identity(r['provider_body']) for r in plan['requests']}):
        raise ValueError('Historical request replay forbidden')
    return {'historical_bodies':len(old_bodies),'overlap':0}


def runtime():
    paths = list((ROOT/'src/vao/repair').glob('*.py')) + [ROOT/'src/vao/decisions/verification.py',
        ROOT/PROTOCOL,ROOT/CONFIG,ROOT/AMENDMENT,ROOT/'scripts/repair_spectrum_study.py',ROOT/'pyproject.toml',ROOT/'uv.lock']
    return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}


def validate_config(config):
    if (config['study']!=STUDY or config['status']!='authorized_separate_development_screen'
            or config['live_calls_enabled'] is not True or dollars(config['allocation_usd'])!=CAP
            or dollars(config['prior_committed_usd'])!=CARRY or config['prior_unresolved_reserves']!=14
            or config['maximum_requests']!=48 or config['minimum_request_interval_seconds']!=60
            or config['resume_allowed'] or config['retries']!=0 or config['key_rotation']
            or dollars(config['cumulative_cap_usd'])!=Decimal('.60')
            or not config.get('authorization_reference')
            or dollars(config['prior_research_commitment_usd'])+dollars(config['minimal_availability_check_usd'])!=CARRY):
        raise ValueError('Authorization differs from declared screen')


def freeze(plan, output, parent=None):
    validate_plan(plan)
    config = read(ROOT/CONFIG)
    validate_config(config)
    f = {'study':STUDY,'plan':plan,'config':config,'overlap_check':no_overlap(plan),
         'source_commit':source_commit(),'runtime':runtime(),'created_utc':datetime.now(timezone.utc).isoformat()}
    if parent is not None:
        f['implementation_correction']=validate_parent(parent,plan)
    f['freeze_id'] = identity(f)
    save(output,f)
    return {'freeze_id':f['freeze_id'],'source_commit':f['source_commit'],'requests':48,**f['overlap_check']}


def validate_freeze(frozen, current=False):
    if frozen['study']!=STUDY or frozen['freeze_id']!=identity({k:v for k,v in frozen.items() if k!='freeze_id'}):
        raise ValueError('Invalid freeze identity')
    validate_config(frozen['config'])
    validate_plan(frozen['plan'])
    if current and (frozen['source_commit']!=source_commit() or frozen['runtime']!=runtime()
                    or frozen['config']!=read(ROOT/CONFIG)):
        raise ValueError('Source or protocol changed after freeze')


def evaluate(record, receipt, verifier):
    task = RepairTask.from_dicts(record['public'],record['evaluator'])
    decoded = decode(task,receipt['content'],receipt['finish_reason'],'json_current')
    result = {'decoded':decoded,'public':None,'evaluator':None}
    if decoded['artifact_valid']:
        result['public'] = verifier.check(decoded['files'],task.public['entrypoint'],task.public['public_cases'])
        result['evaluator'] = verifier.check(decoded['files'],task.public['entrypoint'],task.cases('evaluator'))
    return result


def validate_parent(parent, plan):
    """One narrowly bounded correction, never a transport-error continuation."""
    old=read(parent/'manifest.json')['freeze']
    validate_freeze(old)
    terminal=read(parent/'interruption.json')
    if (old['source_commit']!='b96190330a98598ffec353c95988a8a411f5206f'
            or old['freeze_id']!='5dd799d3ffa02a6559b19723d6cd922628ccd0f667950eb9fe17c41efd000657'
            or old['plan']!=plan or 'implementation_correction' in old
            or terminal['exception_type']!='AttributeError' or (parent/'completion.json').exists()
            or rows(parent/'provider-errors.jsonl') or rows(parent/'observations.jsonl')
            or list((parent/'cells').glob('*.json'))):
        raise ValueError('Only the identified post-receipt evaluator defect qualifies')
    bill=accounting(parent,plan)
    if (bill['admitted']!=1 or bill['settled']!=1 or bill['pending'] or bill['cap_exceeded']
            or dollars(bill['known_usd'])!=Decimal('.0004826')
            or any(dollars(terminal[k])!=dollars(bill[k]) for k in ('known_usd','study_committed_usd','cumulative_committed_usd'))):
        raise ValueError('Parent must contain one fully settled receipt and no uncertainty')
    return {'parent_freeze_id':old['freeze_id'],'parent_source_commit':old['source_commit'],
        'files':{p.relative_to(parent).as_posix():digest(p) for p in sorted(parent.rglob('*')) if p.is_file()},
        'imported_attempts':bill['admitted_attempts'],'imported_known_usd':bill['known_usd'],
        'never_sent_attempts':[r['metadata']['attempt_id'] for r in plan['requests'][1:]],
        'new_allocation_usd':'0','authorization_reference':'Standing user request to proceed; documented agent-declared implementation correction only. No paid request is replayed; see SPECTRUM-IMPLEMENTATION-CORRECTION.md.'}


def collect(frozen, output, parent=None):
    validate_freeze(frozen,current=True)
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise ValueError('Private credential required')
    state = read(ROOT/'runs/ACTIVE_RESEARCH_STATE.json')['current_repair_budget']
    correction=validate_parent(parent,frozen['plan']) if parent is not None else None
    if frozen.get('implementation_correction')!=correction:
        raise ValueError('Correction must be frozen against exactly one immutable parent')
    imported=dollars(correction['imported_known_usd']) if correction else Decimal(0)
    if dollars(state['cumulative_committed_usd'])!=CARRY+imported or state['total_unresolved_reservations']!=14 or state['active_collectors']:
        raise ValueError('Cumulative accounting or active collector changed')
    if output.exists():
        raise ValueError('Output cannot be resumed')
    claims = ROOT/'runs/repair-spectrum-admissions'
    claims.mkdir(exist_ok=True)
    claim_name=STUDY+('-implementation-correction-1' if correction else '')
    save(claims/(claim_name+'.json'),{'freeze_id':frozen['freeze_id'],'output':str(output.resolve()),'resume_allowed':False})
    output.mkdir()
    for name in ('requests','receipts','cells'):
        (output/name).mkdir()
    save(output/'manifest.json',{'freeze':frozen})
    t = StreamingOpenRouterTransport(output,key,SETTINGS,authorized_limit_usd=str(CAP),
        minimum_interval_seconds=60,max_wire_bytes=8388608)
    try:
        if correction:
            # Copy the complete immutable parent before any new provider operation.
            # Its original manifest/interruption remain under parent/. The active
            # ledger imports each old reserve/settlement exactly once.
            shutil.copytree(parent,output/'parent')
            for name in ('requests','receipts','stream-metrics'):
                shutil.copytree(parent/name,output/name,dirs_exist_ok=True)
            shutil.copyfile(parent/'ledger.jsonl',output/'ledger.jsonl')
            t.spent=imported
            t.seen=set(correction['imported_attempts'])
            # Preflight requires seen to be empty; keep imported identities outside
            # that gate, then restore them before the first new admission.
            t.seen.clear()
        verifier = RepairVerifier()
        save(output/'sandbox-preflight.json',verifier.preflight())
        for r in frozen['plan']['records']:
            p = r['public']
            actual = verifier.check(p['files'],p['entrypoint'],p['public_cases'])
            if public_feedback(actual)!=r['stored']['feedback']:
                raise ValueError('Frozen checkpoint feedback does not reproduce')
        t.preflight()
        seen = set()
        start=0
        if correction:
            t.seen=set(correction['imported_attempts'])
            old=frozen['plan']['requests'][0];meta=old['metadata'];attempt=meta['attempt_id']
            receipt=read(output/'receipts'/(attempt+'.json'))
            seen.add(receipt['generation_id'])
            cell=evaluate(frozen['plan']['records'][meta['task_index']],receipt,verifier)
            save(output/'cells'/(attempt+'.json'),{'metadata':meta,**cell})
            append(output/'observations.jsonl',{'attempt_id':attempt,'cell_sha256':digest(output/'cells'/(attempt+'.json'))})
            start=1
        for request in frozen['plan']['requests'][start:]:
            if runtime()!=frozen['runtime']:
                raise ValueError('Frozen runtime changed')
            meta = request['metadata'];attempt = meta['attempt_id']
            save(output/'requests'/(attempt+'.json'),request)
            receipt = t.complete(request['request'],meta)
            if receipt['generation_id'] in seen:
                raise ProviderStopped('Duplicate generation identity')
            seen.add(receipt['generation_id'])
            cell = evaluate(frozen['plan']['records'][meta['task_index']],receipt,verifier)
            save(output/'cells'/(attempt+'.json'),{'metadata':meta,**cell})
            append(output/'observations.jsonl',{'attempt_id':attempt,'cell_sha256':digest(output/'cells'/(attempt+'.json'))})
        validate_freeze(frozen,current=True)
    except Exception as exc:
        save(output/'interruption.json',{'exception_type':type(exc).__name__,'resume_allowed':False,
            'known_usd':str(t.spent),'pending':{k:str(v) for k,v in t.pending.items()},
            'study_committed_usd':str(t.conservative_committed_usd),
            'cumulative_committed_usd':str(CARRY+t.conservative_committed_usd)})
        return {'status':'interrupted','exception_type':type(exc).__name__,'resume_allowed':False}
    save(output/'completion.json',{'observed':48,'known_usd':str(t.spent),'pending':{},
        'study_committed_usd':str(t.conservative_committed_usd),
        'cumulative_committed_usd':str(CARRY+t.conservative_committed_usd)})
    return {'status':'complete','observed':48,'known_usd':str(t.spent)}


def accounting(output, plan):
    """Operational only: no treatment results, safe while collection is active."""
    schedule = {r['metadata']['attempt_id']:r for r in plan['requests']}
    order, pending, settled, ids = [], {}, {}, set()
    for event in rows(output/'ledger.jsonl'):
        k,amount = event['attempt_id'],dollars(event['usd'])
        if event['currency']!='USD' or k not in schedule:
            raise ValueError('Unknown ledger entry')
        req = schedule[k]
        if event['event']=='reserve':
            if (pending or k in settled or k!=plan['requests'][len(order)]['metadata']['attempt_id']
                    or amount!=SETTINGS.reserve):
                raise ValueError('Admission order, reserve or uniqueness differs')
            if read(output/'requests'/(k+'.json'))!=req or read(output/'requests'/(k+'.provider.json'))!=req['provider_body']:
                raise ValueError('Actual request differs from freeze')
            order.append(k);pending[k]=amount
        elif event['event']=='settle':
            if k not in pending or amount>pending[k]:
                raise ValueError('Invalid settlement')
            raw,receipt = read(output/'receipts'/(k+'.raw.json')),read(output/'receipts'/(k+'.json'))
            metrics = read(output/'stream-metrics'/(k+'.json'))
            if (not metrics['stream_complete'] or not metrics['done_received'] or not metrics['usage_received']
                    or raw['model']!=SETTINGS.model or raw['provider']!=SETTINGS.provider_name
                    or not raw.get('reconstructed_from_sse') or raw['id'] in ids
                    or receipt['generation_id']!=raw['id'] or receipt['attempt_id']!=k
                    or receipt['model']!=raw['model'] or receipt['provider']!=raw['provider']
                    or receipt['usage']!=raw['usage'] or dollars(raw['usage']['cost'])!=amount
                    or dollars(receipt['cost_usd'])!=amount
                    or receipt['content']!=raw['choices'][0]['message']['content']
                    or receipt['finish_reason']!=raw['choices'][0]['finish_reason']):
                raise ValueError('Receipt/stream/charge mismatch')
            for field,bound in [('prompt_tokens',SETTINGS.input_token_ceiling),('completion_tokens',SETTINGS.max_tokens)]:
                if type(raw['usage'][field]) is not int or not 0<=raw['usage'][field]<=bound:
                    raise ValueError('Usage exceeds reservation')
            ids.add(raw['id']);settled[k]=amount;del pending[k]
        else:
            raise ValueError('Unknown ledger event')
    for k in pending:
        path = output/'stream-metrics'/(k+'.json')
        if path.exists():
            pending[k]=max(pending[k],dollars(read(path).get('reported_cost_usd','0')))
    known,sum_pending = sum(settled.values(),Decimal(0)),sum(pending.values(),Decimal(0))
    return {'admitted':len(order),'settled':len(settled),'pending':{k:str(v) for k,v in pending.items()},
        'known_usd':str(known),'study_committed_usd':str(known+sum_pending),
        'cumulative_committed_usd':str(CARRY+known+sum_pending),
        'cap_exceeded':known+sum_pending>CAP or CARRY+known+sum_pending>Decimal('.60'),
        'settled_attempts':list(settled),'admitted_attempts':order}


def check_saved_suite(result, cases):
    if result is None or len(result['cases'])!=len(cases):
        raise ValueError('Missing verifier cases')
    for actual,case in zip(result['cases'],cases):
        if actual['id']!=case['id'] or type(actual['passed']) is not bool or actual['passed']!=score(case,actual['observed']):
            raise ValueError('Saved parent-side score differs')
    passed=sum(c['passed'] for c in result['cases'])
    if result['passed_cases']!=passed or result['total_cases']!=len(cases) or result['passed']!=(passed==len(cases)):
        raise ValueError('Saved aggregate score differs')


def summarize(outcomes):
    """All-selected-cell bounds; missingness cannot pass the development gate."""
    expected={(i,d,a) for i in range(8) for d in range(DRAWS) for a in ARMS}
    if set(outcomes)!=expected or any(v is not None and type(v) is not bool for v in outcomes.values()):
        raise ValueError('All 48 selected cells required')
    summaries={a:{'successes':sum(v is True for (_,_,arm),v in outcomes.items() if arm==a),
                  'missing':sum(v is None for (_,_,arm),v in outcomes.items() if arm==a),'selected':24} for a in ARMS}
    differences=[sum(outcomes[i,d,'spectrum'] is True for i in range(8))-
                 sum(outcomes[i,d,'feedback'] is True for i in range(8)) for d in range(DRAWS)]
    stable=sum(sum(outcomes[i,d,'spectrum'] is True for d in range(DRAWS))>=2 for i in range(8))
    complete=all(v is not None for v in outcomes.values())
    f,s=summaries['feedback'],summaries['spectrum']
    gate=('passed_development_screen' if stable>=3 and all(d>0 for d in differences) else 'failed_development_screen') if complete else 'inconclusive_incomplete_bank'
    return {'arms':summaries,'complete':complete,'spectrum_minus_feedback_per_draw_observed':differences,
        'spectrum_bugs_repaired_in_two_draws':stable,
        'difference_bounds_selected_counts':[s['successes']-f['successes']-f['missing'],s['successes']+s['missing']-f['successes']],
        'paired_observed_spectrum_wins':sum(outcomes[i,d,'spectrum'] is True and outcomes[i,d,'feedback'] is False for i in range(8) for d in range(DRAWS)),
        'paired_observed_feedback_wins':sum(outcomes[i,d,'feedback'] is True and outcomes[i,d,'spectrum'] is False for i in range(8) for d in range(DRAWS)),
        'gate':gate,'selector_training_allowed':False,'confirmatory':False}


def audit(output, replay=False):
    complete, interrupted = (output/'completion.json').exists(),(output/'interruption.json').exists()
    if complete==interrupted:
        raise ValueError('Exactly one terminal file required before outcome analysis')
    frozen=read(output/'manifest.json')['freeze'];validate_freeze(frozen)
    plan=frozen['plan'];bill=accounting(output,plan)
    if 'implementation_correction' in frozen:
        correction=validate_parent(output/'parent',plan)
        if correction!=frozen['implementation_correction']:
            raise ValueError('Imported parent differs from correction freeze')
        old_lines=(output/'parent/ledger.jsonl').read_bytes()
        if not (output/'ledger.jsonl').read_bytes().startswith(old_lines):
            raise ValueError('Parent ledger not imported exactly once')
        for name in ('requests','receipts','stream-metrics'):
            for path in (output/'parent'/name).glob('*'):
                if path.is_file() and path.read_bytes()!=(output/name/path.name).read_bytes():
                    raise ValueError('An imported request, receipt or metric changed')
    terminal=read(output/('completion.json' if complete else 'interruption.json'))
    if any(dollars(terminal[k])!=dollars(bill[k]) for k in ('known_usd','study_committed_usd','cumulative_committed_usd')):
        raise ValueError('Terminal accounting differs')
    error_rows=rows(output/'provider-errors.jsonl')
    if {e['attempt_id'] for e in error_rows}!=set(bill['pending']):
        raise ValueError('Error/reserve records differ')
    observations=rows(output/'observations.jsonl')
    observed={r['attempt_id']:r for r in observations}
    if len(observed)!=len(observations) or not set(observed)<=set(bill['settled_attempts']):
        raise ValueError('Orphan or repeated observation')
    if {p.stem for p in (output/'cells').glob('*.json')}!=set(observed):
        raise ValueError('Orphan cell evidence')
    if complete and (len(observed)!=48 or bill['pending'] or bill['cap_exceeded']):
        raise ValueError('Completion is not a complete in-budget bank')
    verifier=RepairVerifier() if replay else None
    if verifier:
        verifier.preflight()
    outcomes,details={},[]
    for request in plan['requests']:
        m=request['metadata'];k=m['attempt_id'];record=plan['records'][m['task_index']]
        result=None;detail={**m,'status':'missing','full_pass':None,'false_acceptance':None,'public_regressions':None}
        if k in observed:
            path=output/'cells'/(k+'.json');cell=read(path)
            if digest(path)!=observed[k]['cell_sha256'] or cell['metadata']!=m:
                raise ValueError('Cell identity differs')
            receipt=read(output/'receipts'/(k+'.json'))
            task=RepairTask.from_dicts(record['public'],record['evaluator'])
            decoded=decode(task,receipt['content'],receipt['finish_reason'],'json_current')
            if cell['decoded']!=decoded:
                raise ValueError('Saved output decoding differs')
            result=False;regressions=None;false_acceptance=False
            if decoded['artifact_valid']:
                for channel,cases in [('public',record['public']['public_cases']),('evaluator',record['evaluator']['cases'])]:
                    check_saved_suite(cell[channel],cases)
                    if verifier and public_feedback(verifier.check(decoded['files'],record['public']['entrypoint'],cases))!=public_feedback(cell[channel]):
                        raise ValueError('Independent execution differs')
                result=cell['public']['passed'] and cell['evaluator']['passed']
                false_acceptance=cell['public']['passed'] and not cell['evaluator']['passed']
                regressions=sum(old['passed'] and not new['passed'] for old,new in zip(record['stored']['feedback']['cases'],cell['public']['cases']))
            elif cell['public'] is not None or cell['evaluator'] is not None:
                raise ValueError('Invalid artifact cannot carry verification')
            detail.update(status='observed',full_pass=result,false_acceptance=false_acceptance,
                public_regressions=regressions,artifact_valid=decoded['artifact_valid'],cost_usd=receipt['cost_usd'],
                prompt_tokens=receipt['usage']['prompt_tokens'],completion_tokens=receipt['usage']['completion_tokens'],
                generation_seconds=receipt['elapsed_seconds'],
                public_verification_seconds=cell['public']['verifier_seconds'] if cell['public'] else 0,
                evaluator_verification_seconds=cell['evaluator']['verifier_seconds'] if cell['evaluator'] else 0)
        detail.update(source_prefix_cost_usd=record['source_prefix_cost_usd'],
            acquisition_executions=record['acquisition']['additional_executions'] if m['arm']=='spectrum' else 0,
            acquisition_seconds=record['acquisition']['seconds'] if m['arm']=='spectrum' else 0)
        details.append(detail);outcomes[m['task_index'],m['draw'],m['arm']]=result
    return {'study':STUDY,**summarize(outcomes),'accounting':bill,'cells':details,
        'candidate_inventory':plan['candidate_inventory'],'source_commit':frozen['source_commit'],
        'independent_replay':replay,'historical_reserves_preserved':14,
        'implementation_correction':frozen.get('implementation_correction'),
        'limitation':'Exposed clustered development cases, fixed one-attempt arms. No equal-total-resource policy or generalization claim.'}


def render(report):
    lines=['# Public coverage after a failed repair', '',
        'Prospective generation screen on eight previously exposed failure checkpoints; twelve source candidates retained.', '',
        '| Arm | Full repairs / selected | Missing | Public false acceptances | Observed API USD |',
        '| --- | ---: | ---: | ---: | ---: |']
    for arm in ARMS:
        s=report['arms'][arm];cells=[r for r in report['cells'] if r['arm']==arm]
        cost=sum((dollars(r['cost_usd']) for r in cells if r['status']=='observed'),Decimal(0))
        lines.append(f"| {arm} | {s['successes']} / 24 | {s['missing']} | {sum(r['false_acceptance'] is True for r in cells)} | {cost} |")
    lines += ['',f"Development screen: **{report['gate']}**.",
        f"Spectrum minus feedback full-repair count bounds over all selected cells: {report['difference_bounds_selected_counts']}.",
        f"Observed differences by draw (missing cells are not imputed): {report['spectrum_minus_feedback_per_draw_observed']}.",
        f"Paired observed wins: spectrum {report['paired_observed_spectrum_wins']}, feedback {report['paired_observed_feedback_wins']}.",
        f"Independent sandbox replay: {report['independent_replay']}.", '',
        f"Known study charges: ${report['accounting']['known_usd']}; conservative study commitment: ${report['accounting']['study_committed_usd']}.",
        f"Cumulative commitment including fourteen historical uncertain reserves: ${report['accounting']['cumulative_committed_usd']} / $0.60.", '',
        '## Interpretation limits', '',
        '- Seven selected bugs are from youtube-dl and one from HTTPie; this is development, not unseen evaluation.',
        '- The effect is for the complete diagnostic package; there is no length-matched placebo or isolation of the ranking formula.',
        '- Both arms have one generation opportunity with the same token limits; realized spend and acquisition work differ.',
        '- Spectrum actions incur twelve extra executions per checkpoint and their measured acquisition time even when the research cache is shared.',
        '- Four historical candidates passing public tests have no recovery trigger; no full-repair inference is made for them here.',
        '- Invalid outputs, false acceptances, regressions and missing cells remain in analysis.json; missingness makes the screen inconclusive.',
        '- A successful screen only supports independent replication and an equal-total-resource policy experiment. No selector is trained.',
        '- Earlier studies and their unknown charges remain closed; current availability does not explain the historical 429.', '',
        'See [protocol](../../SPECTRUM-PROTOCOL.md) for the prespecified screen and [analysis](analysis.json) for every cell.', '']
    if report.get('implementation_correction'):
        lines += ['One paid response preceded a local evaluator API defect. The response was retained and scored offline after correcting the accessor; only the 47 originally frozen, never-sent requests followed. Prompts, ordering, models, seeds, criteria and budget did not change. The immutable parent and exact exception are included in evidence and the [implementation correction](../../SPECTRUM-IMPLEMENTATION-CORRECTION.md).', '']
    return '\n'.join(lines)


def publish(collection, output):
    """Offline terminal delivery; run the independent sandbox replay exactly once."""
    report=audit(collection,replay=True)
    if output.exists():
        raise ValueError('Publication destination must be new')
    output.mkdir(parents=True)
    save(output/'analysis.json',report)
    (output/'REPORT.md').write_text(render(report))
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(9,3.6),layout='constrained')
    colors=['#55799e','#d37b36']
    for x,arm in enumerate(ARMS):
        s=report['arms'][arm]
        axes[0].bar(x,s['successes'],color=colors[x])
        axes[0].bar(x,s['missing'],bottom=s['successes'],color='#dddddd',hatch='//',label='Missing' if x==0 and s['missing'] else None)
        axes[0].text(x,s['successes']+.3,f"{s['successes']}/24",ha='center')
    axes[0].set(xticks=[0,1],xticklabels=list(ARMS),ylim=(0,27),ylabel='Full repairs / selected cells',title='Observed repairs; missing cells hatched')
    for x,arm in enumerate(ARMS):
        ys=[sum(r['full_pass'] is True for r in report['cells'] if r['arm']==arm and r['draw']==d) for d in range(3)]
        axes[1].plot([1,2,3],ys,marker='o',label=arm,color=colors[x])
    axes[1].set(xticks=[1,2,3],ylim=(-.2,8.8),xlabel='Generation draw',ylabel='Observed full repairs / 8',title='Development counts, no uncertainty intervals')
    axes[1].legend()
    fig.savefig(output/'results.png',dpi=180)
    plt.close(fig)
    frozen=read(collection/'manifest.json')['freeze']
    with zipfile.ZipFile(output/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(collection.rglob('*')):
            if path.is_file():
                z.write(path,'collection/'+path.relative_to(collection).as_posix())
        for name,sha in frozen['runtime'].items():
            path=ROOT/name
            if digest(path)!=sha:
                raise ValueError('Frozen source unavailable for inert evidence export')
            z.write(path,'source/'+name+'.txt')
    save(output/'manifest.json',{p.name:digest(p) for p in output.iterdir() if p.is_file()})
    return {k:v for k,v in report.items() if k not in ('cells','candidate_inventory')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','freeze','live','progress','audit','replay','publish'])
    p.add_argument('--input',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--parent',type=Path,help='Only the explicitly frozen local evaluator correction; never a transport retry')
    args=p.parse_args()
    if args.action=='prepare':
        plan=build_plan();validate_plan(plan);check=no_overlap(plan);save(args.output,plan)
        result={'plan_id':plan['plan_id'],'requests':48,'cap_usd':str(CAP),
                'maximum_reservations_usd':plan['maximum_reservations_usd'],**check}
    elif args.action=='freeze':
        result=freeze(read(args.input),args.output,parent=args.parent)
    elif args.action=='live':
        result=collect(read(args.input),args.output,parent=args.parent)
    elif args.action=='progress':
        plan=read(args.input/'manifest.json')['freeze']['plan']
        result=accounting(args.input,plan)
        result={k:v for k,v in result.items() if k not in ('admitted_attempts','settled_attempts')}
    elif args.action=='publish':
        result=publish(args.input,args.output)
    else:
        result=audit(args.input,replay=args.action=='replay')
        if args.output:
            save(args.output,result)
        result={k:v for k,v in result.items() if k not in ('cells','candidate_inventory')}
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
