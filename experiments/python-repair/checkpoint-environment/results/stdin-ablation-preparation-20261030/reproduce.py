"""Audit two complete offline preparation banks; optional native case replay.

Default mode executes no candidate, archived implementation, model or network call.
"""
import argparse
import base64
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from vao.repair import stdin_ablation as ablation
from vao.repair.stdin_verifier import StdinVerifier
from vao.repair.stdin_monitoring import MonitoringStdinVerifier
from prepare_stdin_ablation import Statement


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    raw = (HERE / 'evidence.zip').read_bytes()
    if sha(raw) != manifest['archive_sha256']:
        raise ValueError('Evidence archive changed')
    receipt = (HERE / 'native-replay.txt').read_bytes()
    if (sha(receipt) != manifest['native_replay_receipt_sha256'] or json.loads(receipt.splitlines()[-1]) != {
            'native_replayed_case_executions': 492, 'preflight_executions': 4,
            'discrepancies': 0, 'new_model_calls': 0}):
        raise ValueError('Native replay receipt changed')
    with zipfile.ZipFile(HERE / 'evidence.zip') as z:
        if sorted(z.namelist()) != sorted(manifest['members']):
            raise ValueError('Archive inventory changed')
        blobs = {n: z.read(n) for n in z.namelist()}
    for n, b in blobs.items():
        if n.startswith('/') or '..' in PurePosixPath(n).parts or sha(b) != manifest['members'][n]:
            raise ValueError('Invalid archive member')
    banks = {}
    for name in ('legacy', 'monitoring'):
        plan = json.loads(blobs[name + '/plan.json'])
        end = json.loads(blobs[name + '/completion.json'])
        rows = [json.loads(line) for line in blobs[name + '/records.jsonl'].splitlines()]
        phases = [json.loads(line) for line in blobs[name + '/phase-journal.jsonl'].splitlines()]
        if (end['status'] != 'completed' or end['plan_sha256'] != sha(blobs[name + '/plan.json'])
                or end['new_model_calls'] != 0 or end['completed_tasks'] != len(plan['tasks'])
                or plan['provider_call_enabled'] is not False or plan['new_model_calls'] != 0
                or len(rows) != len(plan['tasks']) or len(phases) != 2*len(rows)):
            raise ValueError('Incomplete or changed preparation bank')
        for n, h in plan['implementation_sha256'].items():
            if sha(blobs[name + '/implementation/' + n + '.txt']) != h:
                raise ValueError('Frozen implementation mismatch')
        banks[name] = {'plan': plan, 'completion': end, 'rows': rows, 'phases': phases}
    comparison = json.loads(blobs['comparison-plan.json'])
    if comparison['legacy_plan_sha256'] != sha(blobs['legacy/plan.json']):
        raise ValueError('Comparison was not bound to the historical bank')
    if not (banks['legacy']['completion']['finished_utc'] < comparison['created_utc']
            < banks['monitoring']['completion']['started_utc']):
        raise ValueError('Engineering comparison chronology changed')
    return banks


def audit_parent(plan):
    parent = HERE.parent / 'fixeval-source-qualification-20261030'
    if (sha((parent / 'evidence.zip').read_bytes()) != plan['qualification_archive_sha256']
            or sha((parent / 'analysis.json').read_bytes()) != plan['qualification_analysis_sha256']):
        raise ValueError('Qualification provenance changed')
    with zipfile.ZipFile(parent / 'evidence.zip') as z:
        old = json.loads(z.read('qualification-freeze.json'))
        extraction = json.loads(z.read('source-extraction.json'))['selected']
        decisions = json.loads((parent / 'analysis.json').read_text())['groups']
        kept = [{k: g[k] for k in ('problem_id', 'group_id', 'selected_pair_index')} for g in decisions]
        if kept != plan['all_original_group_decisions'] or len(kept) != 12:
            raise ValueError('Original candidate decisions dropped or changed')
        eligible = [g for g in kept if g['selected_pair_index'] is not None]
        if [(g['problem_id'], g['selected_pair_index']) for g in eligible] != [
                (t['problem_id'], t['pair_index']) for t in plan['tasks']]:
            raise ValueError('Prospective qualification selection changed')
        for task in plan['tasks']:
            group = next(g for g in old['groups'] if g['problem_id'] == task['problem_id'])
            pair = next(p for p in group['pairs'] if p['pair_index'] == task['pair_index'])
            source = base64.b64decode(pair['sources']['buggy']['source_b64'], validate=True)
            entry = extraction['Project_CodeNet/problem_descriptions/' + group['problem_id'] + '.html']
            statement = z.read(entry['path'])
            reader = Statement(); reader.feed(statement.decode('utf-8'))
            cases = [c for c in group['cases'] if c['split'] == 'public']
            expected = {'schema_version': 3, 'instruction': reader.text(),
                        'files': {'main.py': source.decode('utf-8')}, 'comparator': 'ascii_whitespace_tokens',
                        'public_cases': [{'id': f'case_{i:03}',
                                          'stdin': base64.b64decode(c['input_b64'], validate=True).decode('utf-8'),
                                          'expected_stdout': base64.b64decode(c['expected_b64'], validate=True).decode('utf-8')}
                                         for i, c in enumerate(cases, 1)]}
            if (expected != task['public'] or sha(source) != task['source_sha256']
                    or sha(statement) != task['raw_statement_sha256']
                    or task['binding'] != ablation.binding(expected)
                    or task['public_case_origin'] != {p['id']: c['id'] for p, c in zip(expected['public_cases'], cases)}):
                raise ValueError('Public projection leaks or changes qualified source/tests')


def independent_locations(public, row):
    # Independently rescore raw public IO and count associations. No private tests,
    # upstream fix, stored diagnostic metrics or model results determine a score.
    failed, traces = [], []
    for case, old, capture in zip(public['public_cases'], row['stored']['cases'], row['acquisition']['cases'], strict=True):
        observed = old['execution']['observed']
        actual = base64.b64decode(observed['stdout_b64'], validate=True)
        expected = case['expected_stdout'].encode()
        if public['comparator'] == 'ascii_whitespace_tokens':
            actual, expected = actual.split(), expected.split()
        passed = observed['status'] == 'exited' and observed['returncode'] == 0 and actual == expected
        failed.append(not passed)
        coverage = capture['covered']['coverage']
        traces.append(set(map(tuple, coverage['data']['lines'])) if coverage['available'] else set())
    locations = []
    for filename, line in sorted(set().union(*traces)):
        ef = sum(label and (filename, line) in trace for label, trace in zip(failed, traces))
        ep = sum(not label and (filename, line) in trace for label, trace in zip(failed, traces))
        value = Fraction(ef*ef, sum(failed)*(ef+ep))
        locations.append({'file': filename, 'line': line, 'source': public['files'][filename].splitlines()[line-1],
                          'failing_covered': ef, 'passing_covered': ep,
                          'squared_ochiai': [value.numerator, value.denominator]})
    return locations


def audit(banks):
    result = {'kind': 'offline_preparation_not_model_efficacy', 'new_model_calls': 0, 'banks': {}}
    for name, bank in banks.items():
        plan, end = bank['plan'], bank['completion']
        audit_parent(plan)
        summaries, executions = [], 0
        for i, (task, row) in enumerate(zip(plan['tasks'], bank['rows'], strict=True)):
            if row['problem_id'] != task['problem_id'] or row['binding'] != task['binding']:
                raise ValueError('Task order or binding changed')
            if bank['phases'][2*i:2*i+2] != [
                    {'problem_id': row['problem_id'], 'phase': 'observed', 'stored': row['stored']},
                    {'problem_id': row['problem_id'], 'phase': 'acquired', 'acquisition': row['acquisition']}]:
                raise ValueError('Phase journal differs from final observations')
            public = task['public']
            diagnostic = ablation.analyze(public, row['stored'], row['acquisition'])
            if diagnostic != row['diagnostic'] or ablation.triplet(public, row['stored'], row['acquisition']) != row['requests']:
                raise ValueError('Diagnostic or F/N/S request reproduction differs')
            if diagnostic['available'] and independent_locations(public, row) != diagnostic['locations']:
                raise ValueError('Independent exact-score calculation differs')
            for request in row['requests'].values():
                if request['provider_call_enabled'] is not False:
                    raise ValueError('Expected inert requests')
            metrics = diagnostic['metrics']
            category = ('unavailable' if not diagnostic['available'] else 'empty' if not metrics['covered_lines']
                        else 'flat' if metrics['distinct_scores'] == 1 else 'differentiated')
            summaries.append({'problem_id': task['problem_id'], 'category': category,
                              'invalid_or_mismatched_cases': diagnostic['invalid_or_mismatched_cases'], 'metrics': metrics})
            executions += row['stored']['candidate_executions'] + row['acquisition']['candidate_executions']
        if executions != end['candidate_executions'] or executions != plan['planned_observation_executions'] + plan['planned_acquisition_executions']:
            raise ValueError('Execution accounting differs')
        result['banks'][name] = {'tasks': len(summaries), 'original_groups_retained': len(plan['all_original_group_decisions']),
            'candidate_executions': executions, 'preflight_executions': end['preflight']['candidate_executions'],
            'wall_seconds': end['wall_seconds'], 'preflight_seconds': end['preflight_seconds'],
            'complete_diagnostics': sum(r['category'] != 'unavailable' for r in summaries),
            'categories': {c: sum(r['category'] == c for r in summaries) for c in ('differentiated', 'flat', 'empty', 'unavailable')},
            'groups': summaries}
    comparison = {'public_states': 0, 'ordinary_pairs': 0, 'ordinary_mismatches': [],
                  'covered_vs_ordinary_pairs': 0, 'covered_vs_ordinary_mismatches': [],
                  'complete_legacy_coverage_pairs': 0, 'line_set_mismatches': []}
    legacy, monitoring = banks['legacy'], banks['monitoring']
    if legacy['plan']['tasks'] != monitoring['plan']['tasks']:
        raise ValueError('Engineering comparison changed public states')
    for old, new in zip(legacy['rows'], monitoring['rows'], strict=True):
        comparison['public_states'] += 1
        for a, b in zip(old['stored']['cases'], new['stored']['cases'], strict=True):
            comparison['ordinary_pairs'] += 1
            if ablation.observable_key(a['execution']['observed']) != ablation.observable_key(b['execution']['observed']):
                comparison['ordinary_mismatches'].append([old['problem_id'], a['id']])
        for a, b in zip(old['acquisition']['cases'], new['acquisition']['cases'], strict=True):
            key = [old['problem_id'], a['id']]
            comparison['covered_vs_ordinary_pairs'] += 1
            if ablation.observable_key(b['ordinary']['observed']) != ablation.observable_key(b['covered']['observed']):
                comparison['covered_vs_ordinary_mismatches'].append(key)
            ac, bc = a['covered']['coverage'], b['covered']['coverage']
            if ac['available']:
                comparison['complete_legacy_coverage_pairs'] += 1
                if not bc['available'] or ac['data']['lines'] != bc['data']['lines']:
                    comparison['line_set_mismatches'].append(key)
    result['comparison'] = comparison
    return result


def reexecute(banks):
    count = 0
    for name, bank in banks.items():
        plan = bank['plan']
        if sys.version != plan['python_version'] or sha(Path(sys.executable).read_bytes()) != plan['python_executable_sha256']:
            raise ValueError('Replay needs exact recorded native interpreter')
        needed = ['src/vao/repair/stdin_verifier.py', 'src/vao/repair/stdin_worker.py',
                  'src/vao/repair/coverage_worker.py', 'src/vao/decisions/verification.py']
        if name == 'monitoring':
            needed += ['src/vao/repair/stdin_monitoring.py', 'src/vao/repair/stdin_monitoring_worker.py',
                       'src/vao/repair/monitoring_coverage.py']
        for n in needed:
            if sha((ROOT / n).read_bytes()) != plan['implementation_sha256'][n]:
                raise ValueError('Native executor changed')
        verifier = (StdinVerifier if name == 'legacy' else MonitoringStdinVerifier)(plan['wall_timeout_seconds'])
        verifier.preflight()
        for task, row in zip(plan['tasks'], bank['rows'], strict=True):
            for case, old, capture in zip(task['public']['public_cases'], row['stored']['cases'], row['acquisition']['cases'], strict=True):
                for covered, prior in [(False, old['execution']), (False, capture['ordinary']), (True, capture['covered'])]:
                    current = verifier.invoke(task['public']['files']['main.py'].encode(), case['stdin'].encode(), coverage=covered)
                    if ablation.observable_key(current['observed']) != ablation.observable_key(prior['observed']):
                        raise ValueError('Native outcome differs: ' + str((name, task['problem_id'], case['id'], covered)))
                    if covered and current['coverage'] != prior['coverage']:
                        raise ValueError('Native coverage differs: ' + str((name, task['problem_id'], case['id'])))
                    count += 1
    print(json.dumps({'native_replayed_case_executions': count, 'preflight_executions': 4,
                      'discrepancies': 0, 'new_model_calls': 0}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reexecute', action='store_true', help='Opt in to 492 native sandbox executions plus four preflight probes')
    args = parser.parse_args()
    banks = load(); result = audit(banks)
    if result != json.loads((HERE / 'analysis.json').read_text()):
        raise ValueError('Published analysis differs')
    print(json.dumps({k: v for k, v in result.items() if k != 'banks'}, indent=2), flush=True)
    if args.reexecute:
        reexecute(banks)


if __name__ == '__main__':
    main()
