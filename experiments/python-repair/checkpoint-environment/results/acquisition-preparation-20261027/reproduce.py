"""Audit frozen public acquisition evidence without executing candidates or APIs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from vao.repair.acquisition_snapshot import load, projected
from vao.repair.diagnostic_study import source_records, ARCHIVE_SHA
from vao.repair.environment import RepairTask, identity

HERE=Path(__file__).resolve().parent


def audit():
    manifest=json.loads((HERE/'evidence-manifest.json').read_text())
    archive=HERE/'evidence.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
    with tempfile.TemporaryDirectory(prefix='frozen-acquisition-audit-') as temp, zipfile.ZipFile(archive) as z:
        names=z.namelist()
        assert len(names)==len(set(names)) and set(names)==set(manifest['files'])
        assert sum(i.file_size for i in z.infolist()) < 10000000
        for name in names:
            p=PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and p.parts[0] in ('preparation','source','inputs')
            assert hashlib.sha256(z.read(name)).hexdigest()==manifest['files'][name]
            if p.parts[0]=='preparation':
                path=Path(temp)/p;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
        root=Path(temp)/'preparation';summary=json.loads((root/'summary.json').read_text())
        assert summary==json.loads((HERE/'summary.json').read_text())
        for source,digest in summary['runtime'].items():
            assert hashlib.sha256(z.read('source/'+source+'.txt')).hexdigest()==digest
        pools={}
        for pool,digest in summary['pools'].items():
            raw=z.read('inputs/'+Path(pool).name+'/pool.json')
            assert hashlib.sha256(raw).hexdigest()==digest
            for task in json.loads(raw)['tasks']:
                assert task['id'] not in pools
                pools[task['id']]=(task,digest)
        seen=set()
        for row in summary['records']:
            slug=row['id'];assert slug not in seen;seen.add(slug)
            folder=root/slug
            public=json.loads((folder/'public.json').read_text());state=json.loads((folder/'observation.json').read_text())
            p,digest=pools[slug]
            assert digest==row['pool_sha256']
            code=public['files']['solution.py'];suffix='\n\n'+p['wrappers']['buggy']
            assert code.startswith(p['prefix']) and code.endswith(suffix)
            body=code[len(p['prefix']):-len(suffix)]
            assert hashlib.sha256(body.encode()).hexdigest()==p['provenance']['sources']['buggy']['excerpt_sha256']
            assert public['instruction']==p['instruction'] and public['public_cases']==p['public_cases']
            task=RepairTask.from_dicts(public,{'cases':p['evaluator_cases']})
            assert task.task_hash==row['task_hash']
            snapshot=load(folder/'acquisition',public,public['files'],state,expected_runtime=summary['runtime'])
            assert snapshot['snapshot_id']==row['snapshot_id']
            assert snapshot['diagnostic']['available']==row['available']
            requests=json.loads((folder/'requests.json').read_text())
            for arm,request in requests.items():
                actual=projected(folder/'acquisition',public,public['files'],state,arm,expected_runtime=summary['runtime'])
                assert actual==request and identity(actual['messages'])==row['messages_sha256'][arm]
                assert actual['provider_call_enabled'] is False
                assert sum(len(m['content'].encode()) for m in actual['messages'])+4096==row['conservative_message_byte_plus_framing_allowance'][arm]
            left,right=[json.loads(requests[a]['messages'][1]['content']) for a in ('focused','focused_trace')]
            right.pop('runtime_diagnostic');assert left==right
            assert row['diagnostic_additional_executions']==snapshot['diagnostic']['additional_executions']
            assert row['diagnostic_seconds']==snapshot['diagnostic']['diagnostic_seconds']
            assert row['shared_public_verification_seconds']==state['verifier_seconds']
        assert seen==set(pools) and len(seen)==summary['candidates']==summary['eligible']==summary['available']==8
        assert all(r['eligible_public_failure'] for r in summary['records'])
    assert hashlib.sha256((HERE/'original-checkpoint-headroom.json.gz').read_bytes()).hexdigest()==manifest['headroom_report_sha256']
    assert hashlib.sha256((HERE/'original-headroom-source.py.txt').read_bytes()).hexdigest()==manifest['headroom_source_sha256']
    head=json.loads(gzip.decompress((HERE/'original-checkpoint-headroom.json.gz').read_bytes()))
    assert head['source_archive_sha256']==ARCHIVE_SHA and head['all_original_candidates_retained']==12
    originals=source_records()
    assert len(originals)==len(head['rows'])==12
    different=[];identical=[]
    for row,original in zip(head['rows'],originals):
        assert row['public']==original['public'] and row['source_attempt']==original['source_attempt_id']
        assert row['observation']['feedback']==original['source_public_result']
        if row['eligible']:
            old=row['tail']['trace_result'];new=row['balanced']['trace_result']
            assert old['available'] and new['available'] and old['observed']==new['observed']
            a=old['trace']['events'];b=[{k:v for k,v in e.items() if k not in ('sequence','function_line')} for e in new['trace']['events']]
            assert row['comparison']['same_event_values']==(a==b)
            (identical if a==b else different).append(row['task'])
    assert len(identical)==7 and len(different)==1
    return {'retained_original_sources':12,'original_eligible':8,'original_identical_event_values':len(identical),
            'original_changed_event_values':different,'new_public_snapshots_verified':8,
            'matched_inert_prompts_verified':16,'provider_calls_enabled':False,'candidate_executions':0,
            'archive_sha256':manifest['archive_sha256'],'source_runtime_files_verified':len(summary['runtime']),
            'claim':'Frozen recorded diagnostics and unchanged prompt cores; no repair-benefit or equal-budget result.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=audit()
    if args.output:
        with args.output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
