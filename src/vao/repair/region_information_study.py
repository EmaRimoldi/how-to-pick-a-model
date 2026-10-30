"""Separately funded information-value calibration using actual frozen acquisitions."""
from dataclasses import asdict
from decimal import Decimal
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import zipfile

from .acquisition_snapshot import validate as validate_acquisition
from .contracts import SNAPSHOT_TRACE_STUDY, provenance, public_feedback, study_settings
from .contrastive_study import HISTORY as OLD_HISTORY
from .diagnostics import project, selected_failure
from .environment import RepairTask, identity
from .independent_information_study import archived_requests
from .independent_streaming import POLICY
from .records import save
from .verifier import RepairVerifier

BASE = 'experiments/python-repair/checkpoint-environment'
SOURCE = BASE + '/results/acquisition-preparation-20261027'
ARCHIVE_SHA = '353394a00c57f206c7f29d647ba722cc3731f1c61083bb39672f814c674f00e3'
PRIOR = BASE + '/results/coverage-prefix-20261027'
PRIOR_ARCHIVE_SHA = '4a6566e915f14e736b241778253c2fdb963c09edc6076c0d941100eb76d403e9'
HISTORY = {**OLD_HISTORY,
    BASE+'/results/contrastive-calibration-20261026/evidence.zip': '3205581a96e28f215cae5b23122cda831888c231ccd1a2b04b1eb69af61ac1a6',
    PRIOR+'/evidence.zip': PRIOR_ARCHIVE_SHA}
IDS = ('scrapy-002', 'scrapy-036', 'luigi-010', 'tornado-005', 'thefuck-022', 'thefuck-029', 'scrapy-026', 'scrapy-040')
ARMS = ('focused', 'focused_trace')
DRAWS, SEED = 2, 43139
CARRY = Decimal('0.20937371')


def design():
    return {'arms': list(ARMS), 'draws_per_arm': DRAWS, 'seed': SEED,
        'primary': 'focused_trace_minus_focused', 'source_contract': 'json_current',
        'checkpoint_kind': 'original_buggy_artifact_after_public_test_failure',
        'acquisition_replicates_per_bug': 1, 'generation_draws_condition_on_saved_acquisition': True,
        'screening': {'requires_complete_bank': True, 'minimum_bugs_with_two_trace_successes': 3,
                     'minimum_net_trace_successes': 4, 'positive_in_each_draw': True},
        'bootstrap_seed': 43140, 'bootstrap_draws': 10000, 'fit_selector': False,
        'historical_controls': False, 'exposed_development_checkpoints': True,
        'wire_limit_bytes': 8388608, 'transport_missing_policy': copy.deepcopy(POLICY),
        'diagnostic_reexecution_before_admission': False,
        'trace_representation': 'function-balanced-temporal-v1'}


def source_records():
    root=Path(SOURCE);archive=root/'evidence.zip';manifest=json.loads((root/'evidence-manifest.json').read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ARCHIVE_SHA or manifest['archive_sha256']!=ARCHIVE_SHA:
        raise ValueError('Acquisition source archive changed')
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(manifest['files']):
            raise ValueError('Acquisition source members changed')
        for name,digest in manifest['files'].items():
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('Acquisition source member changed')
        read=lambda name:json.loads(z.read(name))
        summary=read('preparation/summary.json')
        pool_tasks={}
        for path,digest in summary['pools'].items():
            raw=z.read('inputs/'+Path(path).name+'/pool.json')
            if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Prepared pool differs')
            for t in json.loads(raw)['tasks']:
                if t['id'] in pool_tasks:raise ValueError('Duplicate source task')
                pool_tasks[t['id']]=(t,digest)
        for name,digest in summary['runtime'].items():
            if hashlib.sha256(z.read('source/'+name+'.txt')).hexdigest()!=digest:
                raise ValueError('Acquisition runtime identity differs')
        records=[]
        for row in summary['records']:
            slug=row['id'];prefix='preparation/'+slug+'/'
            public,state=read(prefix+'public.json'),read(prefix+'observation.json')
            claim,snapshot=read(prefix+'acquisition/claim.json'),read(prefix+'acquisition/snapshot.json')
            seal=read(prefix+'acquisition/completion.json');pool,digest=pool_tasks[slug]
            if seal!={'claim_id':identity(claim),'snapshot_id':snapshot['snapshot_id']}:
                raise ValueError('Acquisition lacks its exact completion seal')
            diagnostic=validate_acquisition(claim,snapshot,public,public['files'],state,expected_runtime=summary['runtime'])
            code=public['files']['solution.py'];suffix='\n\n'+pool['wrappers']['buggy']
            if not code.startswith(pool['prefix']) or not code.endswith(suffix):raise ValueError('Source adapter changed')
            body=code[len(pool['prefix']):-len(suffix)]
            if (hashlib.sha256(body.encode()).hexdigest()!=pool['provenance']['sources']['buggy']['excerpt_sha256']
                or public['instruction']!=pool['instruction'] or public['public_cases']!=pool['public_cases']):
                raise ValueError('Original public adapter differs from prepared source')
            evaluator={'cases':pool['evaluator_cases']};task=RepairTask.from_dicts(public,evaluator)
            if (task.task_hash!=row['task_hash'] or digest!=row['pool_sha256']
                or snapshot['snapshot_id']!=row['snapshot_id']):raise ValueError('Prepared source identity differs')
            saved_requests=read(prefix+'requests.json')
            for arm in ARMS:
                if (project(public,public['files'],state,arm,diagnostic)!=saved_requests[arm]
                    or identity(saved_requests[arm]['messages'])!=row['messages_sha256'][arm]):
                    raise ValueError('Frozen acquisition prompt changed')
            records.append({'id':slug,'public':public,'evaluator':evaluator,'observation':state,
                'source_public_result':state['feedback'], 'diagnostic':diagnostic,
                'acquisition_claim':claim,'acquisition_snapshot':snapshot,
                'acquisition_runtime':summary['runtime'],'preparation_resources':row,
                'source_prefix_usd':'0','checkpoint_kind':design()['checkpoint_kind']})
    if tuple(r['id'] for r in records)!=IDS:raise ValueError('Retain all eight prepared source tasks in order')
    return records


def schedule(records):
    pairs=[(i,d) for d in range(DRAWS) for i,_ in enumerate(records)]
    random.Random(SEED).shuffle(pairs)
    return [(i,d,arm) for pos,(i,d) in enumerate(pairs) for arm in (ARMS if pos%2==0 else tuple(reversed(ARMS)))]


def planned_requests(records):
    settings,_=study_settings(SNAPSHOT_TRACE_STUDY);requests=[]
    for index,draw,arm in schedule(records):
        r=records[index];p=r['public']
        request=project(p,p['files'],r['observation'],arm,r['diagnostic'])
        request.update(mode='model_pilot',provider_call_enabled=True,remaining_budget_usd=str(settings.reserve))
        meta={'study':SNAPSHOT_TRACE_STUDY,'trajectory':f'{SNAPSHOT_TRACE_STUDY}-task-{index:03d}-draw-{draw}',
              'phase':'diagnostic_probe','depth':1,'draw':draw,'arm':arm,'contract':'json_current',
              'task_index':index,'task_hash':r['task_hash'],'source_snapshot_id':r['acquisition_snapshot']['snapshot_id']}
        meta['attempt_id']=identity(meta)
        requests.append({'metadata':meta,'request':request,'provider_body':settings.body(request,meta)})
    return requests


def construct(records,verifier=None):
    verifier=verifier or RepairVerifier();settings,limit=study_settings(SNAPSHOT_TRACE_STUDY)
    prepared=[]
    for original in records:
        task=RepairTask.from_dicts(original['public'],original['evaluator']);state=original['observation']
        prepared.append({**original,'task_hash':task.task_hash,'eligible':not state['feedback']['passed'],
            'eligibility_reason':'public_failure',
            'initial_public_result':{**state['feedback'],'verifier_seconds':state['verifier_seconds']}})
    requests=planned_requests(prepared);maximum=settings.reserve*len(requests)
    packet={'schema_version':1,'study':SNAPSHOT_TRACE_STUDY,'status':'draft_not_authorized',
        'api_calls':0,'model_results':False,'live_calls_enabled':False,'monetary_authorization_usd':None,
        'provider_settings':asdict(settings),'design':design(),'source_archive_sha256':ARCHIVE_SHA,'source_result':SOURCE,
        'prior_result':PRIOR,'prior_archive_sha256':PRIOR_ARCHIVE_SHA,
        'source_provenance':provenance([RepairTask.from_dicts(r['public'],r['evaluator']) for r in prepared],SNAPSHOT_TRACE_STUDY),
        'verifier_preflight':verifier.preflight(),'tasks':prepared,'requests':requests,'maximum_calls':len(requests),
        'maximum_new_reservations_usd':str(maximum),'proposed_cap_usd':str(limit),'reservation_usd':str(settings.reserve),
        'closed_pilot_commitment_usd':str(CARRY),'maximum_cumulative_commitment_usd':str(CARRY+maximum)}
    packet['packet_id']=identity(packet);validate_packet(packet);return packet


def validate_diagnostics(packet,verifier=None):
    """Validate the stored acquisition and projection, never execute another trace."""
    for r in packet['tasks']:
        p=r['public'];d=validate_acquisition(r['acquisition_claim'],r['acquisition_snapshot'],p,p['files'],r['observation'],
                                            expected_runtime=r['acquisition_runtime'])
        if d!=r['diagnostic'] or r['source_public_result']!=r['observation']['feedback']:
            raise ValueError('Frozen acquisition or feedback differs')


def validate_packet(packet):
    settings,limit=study_settings(SNAPSHOT_TRACE_STUDY)
    if (packet['study']!=SNAPSHOT_TRACE_STUDY or packet['schema_version']!=1
        or packet['packet_id']!=identity({k:v for k,v in packet.items() if k!='packet_id'})
        or packet['status']!='draft_not_authorized' or packet['api_calls']!=0 or packet['model_results']
        or packet['live_calls_enabled'] or packet['monetary_authorization_usd'] is not None):raise ValueError('Invalid frozen-acquisition packet')
    if (packet['design']!=design() or packet['provider_settings']!=asdict(settings)
        or packet['source_archive_sha256']!=ARCHIVE_SHA or packet['source_result']!=SOURCE
        or packet['prior_result']!=PRIOR or packet['prior_archive_sha256']!=PRIOR_ARCHIVE_SHA):raise ValueError('Snapshot study design changed')
    records=packet['tasks']
    if tuple(r['id'] for r in records)!=IDS:raise ValueError('Retain all eight prepared candidates')
    for r in records:
        task=RepairTask.from_dicts(r['public'],r['evaluator'])
        if (task.task_hash!=r['task_hash'] or r['eligible'] is not True or r['eligibility_reason']!='public_failure'
            or selected_failure(task.public,task.public['files'],r['observation']) is None
            or r['source_public_result']!=public_feedback(r['initial_public_result'])
            or r['source_prefix_usd']!='0' or r['checkpoint_kind']!=design()['checkpoint_kind']):raise ValueError('Source or eligibility changed')
    validate_diagnostics(packet)
    expected=planned_requests(records)
    if packet['requests']!=expected or len(expected)!=32 or packet['maximum_calls']!=32:raise ValueError('Exact 32-cell schedule changed')
    if len({r['metadata']['attempt_id'] for r in expected})!=32 or len({identity(r['provider_body']) for r in expected})!=32:raise ValueError('Repeated request')
    maximum=settings.reserve*32
    if (packet['maximum_new_reservations_usd']!=str(maximum) or packet['reservation_usd']!=str(settings.reserve)
        or packet['proposed_cap_usd']!=str(limit) or maximum>limit or packet['closed_pilot_commitment_usd']!=str(CARRY)
        or packet['maximum_cumulative_commitment_usd']!=str(CARRY+maximum)):raise ValueError('Snapshot study budget changed')
    return {'maximum_calls':32,'retained_candidates':8,'eligible':8}


def validate_origin(packet):
    originals=source_records()
    if len(originals)!=len(packet['tasks']) or any(any(r.get(k)!=v for k,v in original.items()) for original,r in zip(originals,packet['tasks'])):
        raise ValueError('Prepared sources or acquisition bytes differ from their published archive')
    old_ids,old_bodies=set(),set()
    for name,digest in HISTORY.items():
        path=Path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Historical archive changed')
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if member.startswith('collection/') and member.endswith('/manifest.json'):
                    for old in archived_requests(json.loads(z.read(member))):
                        old_ids.add(old['metadata']['attempt_id']);old_bodies.add(identity(old['provider_body']))
    if old_ids&{r['metadata']['attempt_id'] for r in packet['requests']} or old_bodies&{identity(r['provider_body']) for r in packet['requests']}:
        raise ValueError('Historical planned request repeated')
    return {'historical_archives':len(HISTORY),'historical_unique_bodies':len(old_bodies),'historical_overlap':0,'source_candidates_verified':8}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    packet=construct(source_records());origin=validate_origin(packet);save(args.output,packet)
    print(json.dumps({k:packet[k] for k in ('packet_id','maximum_calls','maximum_new_reservations_usd','proposed_cap_usd')}));print(json.dumps(origin))


if __name__=='__main__':main()
