"""Audit qualification evidence without executing data; opt in to native replay."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

from analysis_core import analyze, norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(raw): return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reexecute', action='store_true', help='Also rerun all2076 candidate cases under the native sandbox; no models/network')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text())
    if sha((HERE / 'evidence.zip').read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Evidence archive changed')
    receipt = (HERE / 'native-replay.txt').read_bytes()
    if sha(receipt) != manifest['native_replay_receipt_sha256'] or json.loads(receipt.splitlines()[-1]) != {
            'native_replayed_case_executions': 2076, 'discrepancies': 0, 'new_model_calls': 0}:
        raise ValueError('Native replay receipt changed')
    with zipfile.ZipFile(HERE / 'evidence.zip') as z:
        if sorted(z.namelist()) != sorted(manifest['members']): raise ValueError('Member inventory changed')
        blobs = {name: z.read(name) for name in z.namelist()}
    for name, digest in manifest['members'].items():
        if sha(blobs[name]) != digest or name.startswith('/') or '..' in PurePosixPath(name).parts:
            raise ValueError('Invalid evidence member')
    freeze = json.loads(blobs['qualification-freeze.json'])
    previous = HERE.parent / 'fixeval-source-access-20261030'
    selection_bytes = (previous / 'selected-development.json').read_bytes()
    if sha(selection_bytes) != freeze['selection_sha256']:
        raise ValueError('Prospective development selection changed')
    selected = json.loads(selection_bytes)['groups']
    joined = json.loads(gzip.decompress((previous / 'joined-catalog.json.gz').read_bytes()))
    if [g['problem_id'] for g in freeze['groups']] != [g['selected_problem_id'] for g in selected]:
        raise ValueError('Qualification dropped/reordered a prospectively selected group')
    for group, original in zip(freeze['groups'], selected):
        if ([p['metadata'] for p in group['pairs']] != original['candidate_pairs']
                or group['all_group_ids'] != original['all_group_problem_ids']):
            raise ValueError('Qualification changed original candidate pairs/groups')
        prior_cases = next(r['case_pairs'] for r in joined['rows'] if r['problem_id'] == group['problem_id'])
        if [(c['id'], c['original_output_member']) for c in group['cases']] != [(c['input'], c['output']) for c in prior_cases]:
            raise ValueError('Qualification changed the original test inventory')
        examples = {norm(base64.b64decode(v)) for k,v in group['samples'].items() if k.startswith('Sample Input ')}
        buckets = {sha(norm(base64.b64decode(c['input_b64']))): norm(base64.b64decode(c['input_b64'])) for c in group['cases']}
        public = {k for k,v in buckets.items() if v in examples}
        seed = 'repair-fixeval-public-split-20261030-v1'
        order = sorted(set(buckets)-public, key=lambda k: sha(f'{seed}|{group["problem_id"]}|{k}'.encode()))
        public.update(order[:max(0, (len(buckets)+1)//2-len(public))])
        for case in group['cases']:
            key = sha(norm(base64.b64decode(case['input_b64'])))
            if key != case['group_hash'] or case['split'] != ('public' if key in public else 'evaluator'):
                raise ValueError('Public/evaluator assignment differs from prospective seeded rule')
    for name, digest in freeze['implementation_sha256'].items():
        if sha(blobs['implementation/' + name + '.txt']) != digest: raise ValueError('Frozen implementation differs')
    for name, digest in freeze['input_files_sha256'].items():
        if sha(blobs[name]) != digest: raise ValueError('Frozen input record differs')
    extraction, retrieval = json.loads(blobs['source-extraction.json']), json.loads(blobs['test-retrieval.json'])
    if extraction['missing'] or extraction['rejected'] or not extraction['terminal'] or retrieval['status'] != 'complete':
        raise ValueError('Incomplete selected source/test retrieval')
    for record in [*extraction['selected'].values(), *retrieval['members'].values()]:
        raw = blobs[record['path']]
        if len(raw) != record['bytes'] or sha(raw) != record['sha256']: raise ValueError('Selected source/test bytes differ')
    for group in freeze['groups']:
        for pair in group['pairs']:
            for source in pair['sources'].values():
                if source is not None and base64.b64decode(source['source_b64']) != blobs[extraction['selected'][source['member']]['path']]:
                    raise ValueError('Projected program differs from original source')
        for case in group['cases']:
            for field, name in [('input', case['id']), ('expected', case['original_output_member'])]:
                if base64.b64decode(case[field + '_b64']) != blobs[retrieval['members'][name]['path']]:
                    raise ValueError('Projected case differs from downloaded bytes')
    with tempfile.TemporaryDirectory(prefix='inert-fixeval-evidence-') as temporary:
        root = Path(temporary)
        for name, raw in blobs.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        result = analyze(root)
    if result != json.loads((HERE / 'analysis.json').read_text()): raise ValueError('Qualification analysis differs')
    print(json.dumps({k:v for k,v in result.items() if k != 'groups'}, indent=2), flush=True)
    if not args.reexecute:
        print('Saved-source/test binding and independent rescoring passed; candidate re-execution not requested.')
        return
    # A different interpreter/backend is a separate compatibility study, not a silent replay.
    if sys.version != freeze['python_version'] or sha(Path(sys.executable).read_bytes()) != freeze['python_executable_sha256']:
        raise ValueError('Native replay requires the exact recorded interpreter')
    for name, digest in freeze['implementation_sha256'].items():
        if name.startswith('src/') or name == 'uv.lock':
            if sha((ROOT / name).read_bytes()) != digest: raise ValueError('Native replay implementation changed')
    sys.path.insert(0, str(ROOT / 'src'))
    from vao.repair.stdin_verifier import StdinVerifier, compare_stdout
    verifier = StdinVerifier(freeze['parameters']['wall_timeout_seconds']); verifier.preflight()
    groups = {g['problem_id']: g for g in freeze['groups']}
    count = 0
    for raw in blobs['qualification-run/cases.jsonl'].decode().splitlines():
        row = json.loads(raw); group = groups[row['problem_id']]
        pair = next(p for p in group['pairs'] if p['pair_index'] == row['pair_index'])
        case = next(c for c in group['cases'] if c['id'] == row['case_id'])
        result = verifier.invoke(base64.b64decode(pair['sources'][row['role']]['source_b64']), base64.b64decode(case['input_b64']))
        actual, old = result['observed'], row['execution']['observed']
        score = compare_stdout(actual, base64.b64decode(case['expected_b64']), mode='ascii_whitespace_tokens')
        if score != row['passed'] or any(actual[k] != old[k] for k in ['status', 'returncode', 'stdout_b64']):
            raise ValueError('Native replay differs at ' + str((row['problem_id'], row['pair_index'], row['role'], row['repeat'], row['case_id'])))
        count += 1
    print(json.dumps({'native_replayed_case_executions': count, 'discrepancies': 0, 'new_model_calls': 0}))


if __name__ == '__main__': main()
