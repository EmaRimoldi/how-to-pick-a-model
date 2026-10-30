"""Post-hoc descriptive diagnostic; no calls, inference or engineering-gate changes.
All 36 cells retained. Missing executable artifact gets score 0 by convention,
not a claim that unexecuted tests failed. Mean within-cell test pass fractions
weights each of 12 bugs and 3 contracts equally. Public original baseline only.
"""
import hashlib
import json
import zipfile
from fractions import Fraction
from pathlib import Path

import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path.cwd())
parser.add_argument('--output', type=Path, required=True)
args=parser.parse_args()
ROOT=args.root.resolve()
BASE=ROOT/'experiments/python-repair/checkpoint-environment/results'
records={}
evidence={}
for model,folder in [('4B','contract-deepinfra-20261026'),('12B','contract-gemma12b-20261026'),('27B','contract-gemma27b-20261026')]:
    path=BASE/folder
    manifest=json.loads((path/'evidence-manifest.json').read_text())
    archive=path/'evidence.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
    evidence[model]=manifest['archive_sha256']
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(manifest['files'])
        for name,digest in manifest['files'].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest
        packet=json.loads(z.read('collection/manifest.json'))['freeze']['packet']
        rows=[json.loads(line) for line in z.read('collection/observations.jsonl').splitlines()]
        assert 'collection/pilot-completion.json' in z.namelist(), 'Only complete terminal banks may be compared here'
        assert len(rows)==36
        assert len({(r['task_hash'],r['contract']) for r in rows})==36
        records[model]=[]
        for row in rows:
            task=packet['tasks'][row['task_index']]
            initial=task['initial_public_result']
            record={'task_hash':row['task_hash'],'task_id':task['public']['task_id'],
                    'contract':row['contract'],'usable':all(row['decoded'][k] for k in ['artifact_valid','syntax_valid','declared_entrypoint']),
                    'full_pass':row['full_pass'],
                    'baseline_public_fraction':Fraction(initial['passed_cases'],initial['total_cases'])}
            for channel in ['public','evaluator']:
                ref=row[channel]
                record[channel+'_executed']=ref is not None
                if ref is None:
                    score=Fraction(0)
                else:
                    result=json.loads(z.read(f"collection/cells/{row['attempt_id']}/objects/{ref}.json"))['result']
                    assert result['passed_cases']==sum(c['passed'] for c in result['cases'])
                    score=Fraction(result['passed_cases'],result['total_cases'])
                record[channel+'_fraction']=score
            records[model].append(record)
    records[model].sort(key=lambda r:(r['task_hash'],r['contract']))
assert [(r['task_hash'],r['contract']) for r in records['4B']]==[(r['task_hash'],r['contract']) for r in records['12B']]
assert len({r['task_hash'] for r in records['4B']})==12
for model in ['12B','27B']:
    assert [(r['task_hash'],r['contract']) for r in records['4B']]==[(r['task_hash'],r['contract']) for r in records[model]]

def summary(rows):
    n=len(rows)
    return {'cells':n,'usable':sum(r['usable'] for r in rows),
            'full_successes':sum(r['full_pass'] for r in rows),
            'public_passes':sum(r['public_fraction']==1 for r in rows),
            'public_false_positives':sum(r['public_fraction']==1 and not r['full_pass'] for r in rows),
            'distinct_full_success_tasks':sorted({r['task_id'] for r in rows if r['full_pass']}),
            'mean_public_fraction':float(sum(r['public_fraction'] for r in rows)/n),
            'mean_evaluator_fraction':float(sum(r['evaluator_fraction'] for r in rows)/n),
            'mean_original_public_fraction':float(sum(r['baseline_public_fraction'] for r in rows)/n),
            'public_improved_vs_original':sum(r['public_fraction']>r['baseline_public_fraction'] for r in rows),
            'public_equal_vs_original':sum(r['public_fraction']==r['baseline_public_fraction'] for r in rows),
            'public_worse_vs_original':sum(r['public_fraction']<r['baseline_public_fraction'] for r in rows),
            'unevaluated_artifact_failures_scored_zero':sum(not r['public_executed'] for r in rows)}

out={'kind':'post_hoc_descriptive','method':__doc__,'new_model_calls':0,
     'limitations':['One draw per bug/contract, only 12 previously inspected development bugs.',
                    'Different seeds, order and pacing; 27B uses FP8 while 4B/12B use BF16. Not a pure parameter causal effect.',
                    'Test fractions include already passing cases and are not equivalent to repaired bugs.',
                    'No inference, no selector training, no gate changes.'],
     'archive_sha256':evidence,
     'all_cells':{m:summary(rows) for m,rows in records.items()},
     'by_contract':{m:{c:summary([r for r in rows if r['contract']==c]) for c in ['json_current','json_example','python_text']} for m,rows in records.items()},
     'paired_comparisons':{},'records':records}
for first,second in [('4B','12B'),('12B','27B'),('4B','27B')]:
    comparison=out['paired_comparisons'][second+'_vs_'+first]={}
    for channel in ['public','evaluator']:
        key=channel+'_fraction'
        comparison[channel]={
            'improved':sum(b[key]>a[key] for a,b in zip(records[first],records[second])),
            'equal':sum(b[key]==a[key] for a,b in zip(records[first],records[second])),
            'worse':sum(b[key]<a[key] for a,b in zip(records[first],records[second]))}
target=args.output
with target.open('x') as f: json.dump(out,f,indent=2,default=str); f.write('\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['records','method']},indent=2))
