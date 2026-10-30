"""Offline qualification on all source tasks in a complete development archive.

No API requests or evaluator execution. Output is development engineering evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

from vao.analysis.repair_trace_audit import summarize
from vao.repair.contrastive_diagnostics import acquire, compact_trace, expand_trace, project, select_pair
from vao.repair.environment import canonical
from vao.repair.records import save
from vao.repair.verifier import RepairVerifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit = summarize(args.input)
    args.output.mkdir(parents=True, exist_ok=False)
    verifier = RepairVerifier()
    preflight = verifier.preflight()
    with zipfile.ZipFile(args.input / 'evidence.zip') as archive:
        packet = json.loads(archive.read('collection/manifest.json'))['freeze']['packet']
    rows = []
    started = time.monotonic()
    for index, task in enumerate(packet['tasks']):
        # Explicit projection: evaluator, provenance metadata and source outcomes
        # never enter the worker or the model-facing request.
        public, observation = task['public'], task['observation']
        choice = select_pair(public, public['files'], observation)
        records = {}
        for label, paired in (('single', False), ('paired', True)):
            diagnostic = acquire(public, public['files'], observation, verifier, paired=paired)
            request = project(public, public['files'], observation, diagnostic)
            for record in diagnostic['records']:
                if record['available']:
                    trace = record['trace_result']['trace']
                    if canonical(expand_trace(compact_trace(trace))) != canonical(trace):
                        raise ValueError('Retained trace did not roundtrip')
            records[label] = {'diagnostic': diagnostic, 'request': request}
        payloads = [json.loads(records[k]['request']['messages'][1]['content']) for k in ('single', 'paired')]
        single_runtime, paired_runtime = [p.pop('runtime_diagnostic') for p in payloads]
        if payloads[0] != payloads[1]:
            raise ValueError('Core information differs')
        if single_runtime['available'] and paired_runtime['available'] and canonical(single_runtime['records'][0]) != canonical(paired_runtime['records'][0]):
            raise ValueError('Failing trace changed across separate acquisitions')
        original = task['diagnostic'].get('trace_result', {}).get('trace') if task['diagnostic'] else None
        row = {'task_index': index, 'task': public['task_id'], 'eligible': task['eligible'],
            'failure_case': choice['failure']['case']['id'] if choice else None,
            'passing_case': choice['passing']['case']['id'] if choice and choice['passing'] else None,
            'selection': choice['selection'] if choice else None,
            'single_available': records['single']['diagnostic']['available'],
            'paired_available': records['paired']['diagnostic']['available'],
            'additional_executions': sum(records[k]['diagnostic']['additional_executions'] for k in records),
            'raw_retained_trace_bytes': len(canonical(original).encode()) if original else None,
            'compact_retained_trace_bytes': len(canonical(compact_trace(original)).encode()) if original else None,
            'single_payload_bytes': len(records['single']['request']['messages'][1]['content'].encode()),
            'paired_payload_bytes': len(records['paired']['request']['messages'][1]['content'].encode()),
            'retained_trace_roundtrip': True, 'core_information_identical': True}
        save(args.output / f'task-{index:03d}.json', {'public': public, 'observation': observation, **records})
        rows.append(row)
    paths = ('src/vao/repair/contrastive_diagnostics.py', 'src/vao/repair/diagnostics.py',
        'src/vao/repair/verifier.py', 'src/vao/repair/trace_worker.py', 'scripts/prepare_contrastive_diagnostics.py')
    result = {'kind': 'offline_contrastive_diagnostic_qualification', 'api_calls': 0,
        'source_archive_sha256': audit['archive_sha256'], 'preflight': preflight,
        'source_hashes': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in paths},
        'source_candidates': len(rows), 'eligible_sources': sum(r['eligible'] for r in rows),
        'additional_case_executions': sum(r['additional_executions'] for r in rows),
        'preflight_case_executions': 1, 'qualification_wall_seconds': time.monotonic() - started,
        'single_available': sum(r['single_available'] for r in rows),
        'paired_available': sum(r['paired_available'] for r in rows), 'tasks': rows,
        'limitations': ['Exposed development sources, no repair outcomes or efficacy inference.',
            'A nearby public input is not necessarily a semantically informative contrast.',
            'Delta encoding preserves retained trace values, including omissions; it adds no new runtime types.',
            'No API cost or token-count claim follows from UTF-8 byte counts.',
            'Preparation is not a resource-bounded deployment policy or a paid collection authorization.']}
    save(args.output / 'summary.json', result)
    print(json.dumps({k: result[k] for k in ('api_calls', 'source_candidates', 'eligible_sources',
        'additional_case_executions', 'single_available', 'paired_available')}, indent=2))


if __name__ == '__main__':
    main()
