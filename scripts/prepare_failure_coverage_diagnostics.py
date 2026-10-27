"""Qualify bounded first/all-failure traces on a development pool; no API calls."""
import argparse
import hashlib
import json
from pathlib import Path

from vao.repair.contrastive_diagnostics import compact_trace, expand_trace
from vao.repair.diagnostics import observe, project as baseline
from vao.repair.environment import canonical
from vao.repair.failure_coverage_diagnostics import acquire, project
from vao.repair.pool import read_pool
from vao.repair.records import save
from vao.repair.verifier import RepairVerifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = read_pool(args.pool)
    args.output.mkdir(parents=True, exist_ok=False)
    verifier = RepairVerifier()
    preflight = verifier.preflight()
    results = []
    for slug, task, _reference in rows:
        # Explicit boundary: neither evaluator nor reference enters acquisition.
        public = task.public
        observation = observe(public, public['files'], verifier)
        request = baseline(public, public['files'], observation, 'focused')
        core = json.loads(request['messages'][1]['content'])
        treatments = {}
        for coverage in ('first', 'all'):
            diagnostic = acquire(public, public['files'], observation, verifier, coverage=coverage)
            projected = project(public, public['files'], observation, diagnostic)
            payload = json.loads(projected['messages'][1]['content'])
            payload.pop('runtime_diagnostic')
            if payload != core:
                raise ValueError('Matched core information changed')
            for record in diagnostic['records']:
                if record['available']:
                    trace = record['trace_result']['trace']
                    if canonical(expand_trace(compact_trace(trace))) != canonical(trace):
                        raise ValueError('Retained runtime values changed in encoding')
            treatments[coverage] = {'diagnostic': diagnostic, 'request': projected}
        first = treatments['first']['diagnostic']['records']
        all_records = treatments['all']['diagnostic']['records']
        if first and canonical(first[0]) != canonical(all_records[0]):
            raise ValueError('First failure trace changed across acquisitions')
        save(args.output / (slug + '.json'), {'public': public, 'observation': observation,
            'baseline_request': request, **treatments})
        results.append({'task': slug, 'failed_public_cases': sum(not c['passed'] for c in observation['feedback']['cases']),
            'baseline_message_bytes': sum(len(m['content'].encode()) for m in request['messages']),
            'source_verification_seconds': observation['verifier_seconds'],
            'arms': {k: {'complete': v['diagnostic']['complete'],
                'selected_cases': v['diagnostic']['selected_cases'],
                'additional_executions': v['diagnostic']['additional_executions'],
                'diagnostic_seconds': v['diagnostic']['diagnostic_seconds'],
                'message_bytes': sum(len(m['content'].encode()) for m in v['request']['messages'])}
                for k, v in treatments.items()}})
    sources = ['src/vao/repair/failure_coverage_diagnostics.py', 'scripts/prepare_failure_coverage_diagnostics.py',
        'src/vao/repair/contrastive_diagnostics.py', 'src/vao/repair/diagnostics.py',
        'src/vao/repair/trace_worker.py', 'src/vao/repair/verifier.py']
    report = {'kind': 'offline_public_failure_coverage_qualification', 'api_calls': 0,
        'model_results': False, 'pool_sha256': hashlib.sha256((args.pool / 'pool.json').read_bytes()).hexdigest(),
        'source_hashes': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources},
        'preflight': preflight, 'sources': len(rows), 'tasks': results,
        'core_information_identical': True, 'first_trace_identical': True, 'trace_encoding_roundtrip': True,
        'limitations': ['Development only: no model difficulty or diagnostic-benefit evidence.',
            'Every public case and expected value is already available in all arms.',
            'First/all refer to observed failures in the supplied current artifact; no private oracle is used.',
            'Counts and local timing describe acquisition, not full equal-budget deployment.',
            'Message UTF-8 byte counts are not provider token counts or authorization for a collection.']}
    save(args.output / 'summary.json', report)
    print(json.dumps({'sources': len(rows), 'api_calls': 0, 'tasks': results}, indent=2))


if __name__ == '__main__':
    main()
