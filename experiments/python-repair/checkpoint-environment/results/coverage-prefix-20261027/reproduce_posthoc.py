"""Reproduce descriptive public transitions from the inert evidence archive."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
archive = root / 'evidence.zip'
manifest = json.loads((root / 'evidence-manifest.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist()) == len(set(z.namelist()))
    assert set(z.namelist()) == set(manifest['files'])
    for name, expected in manifest['files'].items():
        assert hashlib.sha256(z.read(name)).hexdigest() == expected
    read = lambda name: json.loads(z.read('collection/' + name))
    packet = read('manifest.json')['freeze']['packet']
    observations = [json.loads(line) for line in z.read('collection/observations.jsonl').splitlines() if line.strip()]
    assert len(observations) == len(packet['tasks']) == 6
    records = []
    for row in observations:
        task = packet['tasks'][row['task_index']]
        obj = lambda key: read('cells/' + row['attempt_id'] + '/objects/' + key + '.json')
        record = {'task': task['public']['task_id'], 'attempt_id': row['attempt_id'],
            'full_pass': row['full_pass'], 'artifact_valid': row['decoded']['artifact_valid']}
        if row['artifact']:
            files = obj(row['artifact'])['files']
            initial = task['initial_public_result']['cases']; current = obj(row['public'])['result']['cases']
            assert [r['id'] for r in initial] == [r['id'] for r in current]
            encoded = json.dumps(files,sort_keys=True,separators=(',', ':'),ensure_ascii=True,allow_nan=False)
            record.update(public_gains=sum(not a['passed'] and b['passed'] for a,b in zip(initial,current)),
                public_losses=sum(a['passed'] and not b['passed'] for a,b in zip(initial,current)),
                source_passed=sum(r['passed'] for r in initial),candidate_passed=sum(r['passed'] for r in current),
                candidate_files_sha256=hashlib.sha256(encoded.encode()).hexdigest())
            errors = []
            for name,code in files.items():
                try: ast.parse(code)
                except SyntaxError as error:
                    errors.append({'file':name,'message':error.msg,'line':error.lineno,'offset':error.offset,'line_text':error.text})
            record['syntax_errors'] = errors
        records.append(record)
report = {'kind':'posthoc_structural_audit_not_a_new_model_outcome','api_calls':0,
    'source_run':'runs/coverage-prefix-model-20261027', 'records':sorted(records,key=lambda r:r['task']),
    'limitations':['Public transitions are descriptive and do not identify unique causes.',
        'No output was edited, repaired, filtered or rescored; original full repair counts remain4/6.',
        'The failure-coverage screen stays failed and stage2 stays disabled.']}
with args.output.open('x') as stream:
    json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps({'records':len(records),'api_calls':0,'output':str(args.output)}))
