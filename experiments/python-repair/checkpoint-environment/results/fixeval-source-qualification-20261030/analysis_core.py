"""Independently score every frozen case and apply the prior qualification rules."""
import base64
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(raw):
    return json.dumps([base64.b64encode(x).decode() for x in raw.split()], separators=(',', ':')).encode()


def analyze(root):
    raw = (root / 'qualification-freeze.json').read_bytes()
    freeze = json.loads(raw)
    terminal = json.loads((root / 'qualification-run/completion.json').read_text())
    if terminal['status'] != 'completed' or terminal['freeze_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('Qualification bank is not complete or not bound to freeze')
    if freeze['parameters']['comparator'] != 'ascii_whitespace_tokens; exact case/number spelling, no float coercion':
        raise ValueError('Unexpected frozen comparator')
    lookup = {}
    for group in freeze['groups']:
        samples = {norm(base64.b64decode(v)) for k, v in group['samples'].items() if k.startswith('Sample Input ')}
        public = {norm(base64.b64decode(c['input_b64'])) for c in group['cases'] if c['split'] == 'public'}
        hidden = {norm(base64.b64decode(c['input_b64'])) for c in group['cases'] if c['split'] == 'evaluator'}
        if public & hidden or samples & hidden:
            raise ValueError('Public/sample input in evaluator split')
        for pair in group['pairs']:
            for role, source in pair['sources'].items():
                if source is None: continue
                if hashlib.sha256(base64.b64decode(source['source_b64'], validate=True)).hexdigest() != source['sha256']:
                    raise ValueError('Source bytes differ from hash')
                for repeat in range(freeze['parameters']['repeat_count']):
                    for case in group['cases']:
                        key = (group['problem_id'], pair['pair_index'], role, repeat, case['id'])
                        if key in lookup: raise ValueError('Duplicate planned execution')
                        lookup[key] = (case, source)
    actual, total_seconds, statuses = {}, 0.0, Counter()
    for line in (root / 'qualification-run/cases.jsonl').read_text().splitlines():
        row = json.loads(line)
        key = tuple(row[k] for k in ['problem_id', 'pair_index', 'role', 'repeat', 'case_id'])
        if key not in lookup or key in actual: raise ValueError('Unplanned/duplicate execution')
        case, source = lookup[key]
        if row['source_sha256'] != source['sha256'] or row['split'] != case['split']:
            raise ValueError('Execution does not match source/case')
        observed = row['execution']['observed']
        stdout = base64.b64decode(observed['stdout_b64'], validate=True)
        expected = base64.b64decode(case['expected_b64'], validate=True)
        for field, value in [('expected', expected), ('input', base64.b64decode(case['input_b64'], validate=True))]:
            if hashlib.sha256(value).hexdigest() != case[field + '_sha256']:
                raise ValueError('Frozen case bytes changed')
        score = observed['status'] == 'exited' and observed['returncode'] == 0 and stdout.split() == expected.split()
        if type(row['passed']) is not bool or row['passed'] != score:
            raise ValueError('Independent parent-side scoring disagrees')
        elapsed = row['execution']['elapsed_seconds']
        if not math.isfinite(elapsed) or elapsed < 0 or row['execution']['candidate_executions'] != 1:
            raise ValueError('Invalid resource accounting')
        if row['execution']['python'] != freeze['python_version'].split()[0]:
            raise ValueError('Wrong executed interpreter')
        total_seconds += elapsed; statuses[observed['status']] += 1
        actual[key] = row
    if set(actual) != set(lookup) or len(actual) != terminal['case_executions']:
        raise ValueError('Incomplete qualification evidence')
    summary, reasons = [], Counter()
    for group in freeze['groups']:
        candidates = []
        for pair in group['pairs']:
            pid, index = group['problem_id'], pair['pair_index']
            failures = list(group['partition_issues'])
            counts = {}
            stable = True
            for role in ['buggy', 'reference']:
                if pair['sources'][role] is None:
                    failures.append('missing_' + role); continue
                for repeat in range(freeze['parameters']['repeat_count']):
                    selected = [actual[(pid, index, role, repeat, c['id'])] for c in group['cases']]
                    counts[f'{role}_{repeat}'] = {split: {'passed': sum(r['passed'] for r in selected if r['split'] == split),
                                                         'total': sum(r['split'] == split for r in selected)}
                                                   for split in ['public', 'evaluator']}
                    if role == 'reference' and not all(r['passed'] for r in selected): failures.append('reference_failed')
                    if role == 'buggy':
                        for split in ['public', 'evaluator']:
                            if all(r['passed'] for r in selected if r['split'] == split): failures.append('buggy_no_' + split + '_failure')
                for case in group['cases']:
                    values = [actual[(pid, index, role, rep, case['id'])] for rep in range(freeze['parameters']['repeat_count'])]
                    # Exact rule: stability of per-case pass and stdout; traceback paths/timings may change.
                    stable &= len({(r['passed'], r['execution']['observed']['stdout_b64']) for r in values}) == 1
            if not stable: failures.append('unstable_pass_or_stdout')
            failures = sorted(set(failures)); reasons.update(failures)
            candidates.append({'pair_index': index, 'eligible': not failures, 'reasons': failures,
                               'counts_by_role_repeat_split': counts,
                               'source_metadata': pair['metadata']})
        chosen = next((c['pair_index'] for c in candidates if c['eligible']), None)
        summary.append({'problem_id': group['problem_id'], 'group_id': group['group_id'],
                        'selected_pair_index': chosen, 'candidates': candidates,
                        'public_cases': sum(c['split'] == 'public' for c in group['cases']),
                        'evaluator_cases': sum(c['split'] == 'evaluator' for c in group['cases'])})
    return {'freeze_sha256': hashlib.sha256(raw).hexdigest(), 'selected_groups': len(summary),
            'executed_python_version': freeze['python_version'],
            'runtime_prose_deviation': 'The parameter prose names CPython3.11; the exact version and binary hash frozen before execution and enforced by the collector were CPython3.13.12. This bank qualifies the recorded actual runtime only; no3.11 replay is claimed.',
            'candidate_pairs': sum(len(g['candidates']) for g in summary),
            'eligible_pairs': sum(c['eligible'] for g in summary for c in g['candidates']),
            'qualified_development_groups': sum(g['selected_pair_index'] is not None for g in summary),
            'case_executions': len(actual), 'preflight_executions': terminal['preflight']['candidate_executions'],
            'execution_status_counts': dict(statuses), 'independent_rescoring_discrepancies': 0,
            'pair_exclusion_reason_counts_nonexclusive': dict(reasons),
            'case_execution_seconds': total_seconds, 'total_wall_seconds_including_preflight': terminal['elapsed_seconds'],
            'new_model_calls': 0, 'policy_or_diagnostic_efficacy_measured': False, 'groups': summary}


if __name__ == '__main__':
    result = analyze(HERE)
    (HERE / 'qualification-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'groups'}, indent=2))
