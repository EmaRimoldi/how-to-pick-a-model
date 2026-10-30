"""Audit both saved offline banks without executing any candidate or calling a model."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

from vao.repair.environment import canonical
from vao.repair.region_verifier import valid_bounds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(prefix, check_current_sources=False):
    report = json.loads((HERE/(prefix+'report.json')).read_text())
    archive = HERE/(prefix+'traces.json.gz')
    assert sha(archive) == report['trace_archive_sha256']
    blobs = json.loads(gzip.decompress((HERE/'source-blobs.json.gz').read_bytes()))
    for name, expected in report['source_manifest'].items():
        assert hashlib.sha256(base64.b64decode(blobs[expected], validate=True)).hexdigest() == expected, name
        if check_current_sources:
            original = HERE/'initial-source'/(name.replace('/', '__')+'.txt')
            path = original if prefix and original.exists() else ROOT/name
            assert sha(path) == expected, name
    details = json.loads(gzip.decompress(archive.read_bytes()))
    assert len(details) == len(report['records']) == report['selected_cases'] == 80
    changes, pairs, larger, same, smaller = [], 0, 0, 0, 0
    observations = {}
    functions_by_task = {}
    for row, detail in zip(report['records'], details):
        key = tuple(row[k] for k in ('task', 'variant', 'case'))
        assert key == tuple(detail[k] for k in ('task', 'variant', 'case')) and key not in observations
        banks = detail['results']
        assert set(banks) == {'ordinary', 'tail', 'balanced'}
        assert all(len(values) == report['repeats'] == 3 for values in banks.values())
        for ordinary, tail, balanced in zip(banks['ordinary'], banks['tail'], banks['balanced']):
            assert ordinary == tail['observed'] == balanced['observed'] == banks['ordinary'][0]
            assert tail['available'] and balanced['available']
            for response in (tail, balanced):
                trace = response['trace']
                assert len(trace['events']) <= 32
                assert sum(len(json.dumps(e, ensure_ascii=True, allow_nan=False).encode()) for e in trace['events']) <= 12000
            assert valid_bounds(balanced['trace'], {'solution.py': ''})
            pairs += 1
        observations[key] = banks['ordinary'][0]
        stable = all(all(value == values[0] for value in values) for values in banks.values())
        assert row['repeat_deterministic'] == stable
        if not stable: changes.append(':'.join(key))
        counts = {k: len({e['function'] for e in banks[k][0]['trace']['events']}) for k in ('tail', 'balanced')}
        larger += counts['balanced'] > counts['tail']
        same += counts['balanced'] == counts['tail']
        smaller += counts['balanced'] < counts['tail']
        functions_by_task.setdefault(key[0], []).append(counts)
    assert report['all_observations_match'] and not report['all_repeats_deterministic']
    assert sorted(changes) == sorted(['thefuck-022:buggy:ordering', 'thefuck-022:fixed:ordering'])
    return {'case_comparisons': 80, 'replicated_observation_agreements': pairs,
            'nondeterministic_trace_cases': changes,
            'function_name_coverage': {'more': larger, 'same': same, 'fewer': smaller},
            'archives_verified': True, 'runtime_and_input_hashes_verified': len(report['source_manifest'])}, observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-current-sources', action='store_true')
    args = parser.parse_args()
    first, observed_first = audit('initial-', args.check_current_sources)
    second, observed_second = audit('', args.check_current_sources)
    assert observed_first == observed_second
    result = {'initial_bank': first, 'second_bank': second, 'observations_match_between_banks': True,
              'new_candidate_executions': 0, 'api_calls': 0,
              'current_sources_checked': args.check_current_sources,
              'source_archive_sha256': sha(HERE/'source-blobs.json.gz'),
              'scope': 'Source/archive identities, observed outcomes, bounded traces and descriptive coverage; not repair benefit or identical stochastic traces.'}
    if args.output:
        with args.output.open('x') as out: out.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
