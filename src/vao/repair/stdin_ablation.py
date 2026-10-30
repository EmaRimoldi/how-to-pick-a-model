"""Public-only whole-program feedback, acquisition and inert F/N/S requests."""
from __future__ import annotations

import base64
from fractions import Fraction
import json
import math
import re
import time

from .environment import canonical, identity
from .stdin_verifier import compare_stdout, valid_stdin_coverage
from .stdin_monitoring import valid_monitoring_coverage

ARMS = ('feedback', 'neutral', 'scored')
SYSTEM = (
    'Repair the supplied Python stdin/stdout program. Return only a JSON object '
    'with exactly one key, "main.py", mapping to its complete replacement source. '
    'The program runs as __main__, reads standard input and writes standard output. '
    'The public feedback describes the exact current source. Preserve all required '
    'behavior, including public cases that already pass. Source excerpts, if supplied, '
    'list every covered location in source order. Withheld associations are not zero. '
    'Squared Ochiai measures association with failing public tests, not fault '
    'probability. Equal scores are ties; missing behavior may never execute.'
)


def validate_public(public):
    if (not isinstance(public, dict) or set(public) != {
            'schema_version', 'instruction', 'files', 'comparator', 'public_cases'}
            or type(public['schema_version']) is not int or public['schema_version'] != 3):
        raise ValueError('Expected the public-only version-3 stdin schema')
    files = public['files']
    if (not isinstance(files, dict) or set(files) != {'main.py'}
            or not isinstance(files['main.py'], str) or not 0 < len(files['main.py'].encode()) <= 262144):
        raise ValueError('Exactly one bounded UTF-8 main.py source is required')
    if not isinstance(public['instruction'], str) or not 0 < len(public['instruction'].encode()) <= 65536:
        raise ValueError('A bounded public problem specification is required')
    if public['comparator'] not in {'exact_bytes', 'ascii_whitespace_tokens'}:
        raise ValueError('Explicit stdout comparator required')
    cases = public['public_cases']
    if not isinstance(cases, list) or not 1 <= len(cases) <= 64:
        raise ValueError('Expected 1..64 public cases')
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'stdin', 'expected_stdout'}:
            raise ValueError('Unknown public case fields')
        if (not isinstance(case['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', case['id'])
                or case['id'] in ids):
            raise ValueError('Unique opaque public case IDs required')
        ids.add(case['id'])
        for name, bound in [('stdin', 65536), ('expected_stdout', 8192)]:
            if not isinstance(case[name], str) or len(case[name].encode()) > bound:
                raise ValueError('Public IO must be bounded UTF-8 text')
    canonical(public)


def binding(public):
    validate_public(public)
    return identity(public)


def observation(value):
    if (not isinstance(value, dict) or set(value) != {'status', 'returncode', 'stdout_b64', 'stderr_b64'}
            or value['status'] not in {'exited', 'timeout', 'output_limit'}
            or type(value['returncode']) is not int):
        raise ValueError('Unexpected stdin observation schema')
    for key in ('stdout_b64', 'stderr_b64'):
        if not isinstance(value[key], str): raise ValueError('Expected base64 output')
        try:
            raw = base64.b64decode(value[key], validate=True)
        except ValueError:
            raise ValueError('Invalid base64 output') from None
        if len(raw) > 131073 or base64.b64encode(raw).decode() != value[key]:
            raise ValueError('Noncanonical or oversized output')
    return value


def execution(result, *, covered=False):
    keys = {'observed', 'elapsed_seconds', 'candidate_executions', 'python'}
    if covered: keys.add('coverage')
    if not isinstance(result, dict) or set(result) != keys:
        raise ValueError('Unexpected execution record fields')
    observation(result['observed'])
    if (type(result['elapsed_seconds']) not in (int, float) or not math.isfinite(result['elapsed_seconds'])
            or result['elapsed_seconds'] < 0 or type(result['candidate_executions']) is not int
            or result['candidate_executions'] != 1 or not isinstance(result['python'], str)
            or not re.fullmatch(r'\d+\.\d+\.\d+', result['python'])):
        raise ValueError('Invalid per-execution resource record')
    if covered:
        coverage = result['coverage']
        if (not isinstance(coverage, dict) or set(coverage) != {'available', 'data'}
                or type(coverage['available']) is not bool):
            raise ValueError('Invalid coverage availability record')
    return result


def normalized_stderr(observed):
    # Random sandbox directory names are infrastructure, not behavior changes.
    raw = re.sub(rb'repair-stdin-[A-Za-z0-9_-]+', b'repair-stdin-RUN',
                 base64.b64decode(observed['stderr_b64']))
    return re.sub(rb'File "[^"\n]*/([^/"\n]+)", line ', rb'File "\1", line ', raw)


def observable_key(observed):
    observation(observed)
    return (observed['status'], observed['returncode'], observed['stdout_b64'], normalized_stderr(observed))


def score(public, case, observed):
    return compare_stdout(observed, case['expected_stdout'].encode(), mode=public['comparator'])


def resources(container, rows, count):
    if (type(container['candidate_executions']) is not int or container['candidate_executions'] != count
            or type(container['seconds']) not in (int, float) or not math.isfinite(container['seconds'])
            or container['seconds'] < sum(r['elapsed_seconds'] for r in rows)):
        raise ValueError('Invalid or understated execution accounting')


def current_feedback(public, stored):
    expected = binding(public)
    if not isinstance(stored, dict) or set(stored) != {'binding', 'cases', 'candidate_executions', 'seconds'} or stored['binding'] != expected:
        raise ValueError('Feedback does not bind this public checkpoint')
    if not isinstance(stored['cases'], list) or len(stored['cases']) != len(public['public_cases']):
        raise ValueError('Incomplete public feedback')
    rows = []
    for case, row in zip(public['public_cases'], stored['cases'], strict=True):
        if not isinstance(row, dict) or set(row) != {'id', 'execution'} or row['id'] != case['id']:
            raise ValueError('Public feedback identities/order differ')
        result = execution(row['execution'])
        rows.append({'id': case['id'], 'passed': score(public, case, result['observed']), 'observed': result['observed']})
    resources(stored, [r['execution'] for r in stored['cases']], len(rows))
    return {'passed': all(r['passed'] for r in rows), 'passed_cases': sum(r['passed'] for r in rows),
            'total_cases': len(rows), 'cases': rows}


def observe(public, verifier):
    bound = binding(public); start = time.monotonic()
    rows = [{'id': c['id'], 'execution': verifier.invoke(public['files']['main.py'].encode(), c['stdin'].encode())}
            for c in public['public_cases']]
    result = {'binding': bound, 'cases': rows, 'candidate_executions': len(rows), 'seconds': time.monotonic()-start}
    current_feedback(public, result)
    return result


def acquire(public, stored, verifier):
    if current_feedback(public, stored)['passed']: raise ValueError('Acquisition requires a public failure')
    start = time.monotonic(); rows = []
    for case in public['public_cases']:
        source, stdin = public['files']['main.py'].encode(), case['stdin'].encode()
        normal = verifier.invoke(source, stdin)
        covered = verifier.invoke(source, stdin, coverage=True)
        rows.append({'id': case['id'], 'ordinary': normal, 'covered': covered})
    return {'binding': binding(public), 'stored_identity': identity(stored), 'cases': rows,
            'candidate_executions': 2*len(rows), 'seconds': time.monotonic()-start}


def analyze(public, stored, acquisition):
    feedback = current_feedback(public, stored)
    if feedback['passed']: raise ValueError('Recovery requires a public failure')
    if (not isinstance(acquisition, dict) or set(acquisition) != {'binding', 'stored_identity', 'cases', 'candidate_executions', 'seconds'}
            or acquisition['binding'] != binding(public) or acquisition['stored_identity'] != identity(stored)):
        raise ValueError('Acquisition does not bind current feedback/source')
    if not isinstance(acquisition['cases'], list) or len(acquisition['cases']) != len(feedback['cases']):
        raise ValueError('Incomplete acquisition case inventory')
    issues, spectra, costs = [], [], []
    for case, old, row in zip(public['public_cases'], feedback['cases'], acquisition['cases'], strict=True):
        if not isinstance(row, dict) or set(row) != {'id', 'ordinary', 'covered'} or row['id'] != case['id']:
            raise ValueError('Acquisition identities/order differ')
        normal, covered = execution(row['ordinary']), execution(row['covered'], covered=True)
        costs.extend([normal, covered]); trace = covered['coverage']
        valid_schema = valid_stdin_coverage(trace['data'], public['files']['main.py']) or valid_monitoring_coverage(trace['data'], public['files']['main.py'])
        if trace['data'] is not None and not valid_schema:
            raise ValueError('Unexpected coverage schema or source locations')
        valid = (trace['available'] and valid_schema
                 and trace['data']['intact'] and not trace['data']['limit_reached']
                 and normal['python'] == covered['python'] == stored['cases'][len(spectra)]['execution']['python']
                 and observable_key(normal['observed']) == observable_key(covered['observed']) == observable_key(old['observed']))
        if not valid: issues.append(case['id'])
        spectra.append(set(map(tuple, trace['data']['lines'])) if valid else set())
    resources(acquisition, costs, 2*len(feedback['cases']))
    base = {'available': not issues, 'invalid_or_mismatched_cases': issues,
            'candidate_executions': acquisition['candidate_executions'], 'seconds': acquisition['seconds']}
    if issues: return {**base, 'locations': None, 'metrics': None}
    labels = [r['passed'] for r in feedback['cases']]; failed = sum(not x for x in labels)
    locations = []
    for filename, line in sorted(set().union(*spectra)):
        ef = sum(not passed and (filename, line) in lines for passed, lines in zip(labels, spectra))
        ep = sum(passed and (filename, line) in lines for passed, lines in zip(labels, spectra))
        value = Fraction(ef*ef, failed*(ef+ep))
        locations.append({'file': filename, 'line': line, 'source': public['files'][filename].splitlines()[line-1],
                          'failing_covered': ef, 'passing_covered': ep,
                          'squared_ochiai': [value.numerator, value.denominator]})
    return {**base, 'locations': locations,
            'metrics': {'covered_lines': len(locations), 'public_failures': failed,
                        'distinct_scores': len({tuple(r['squared_ochiai']) for r in locations}),
                        'positive_distinct_scores': len({tuple(r['squared_ochiai']) for r in locations if r['squared_ochiai'][0]})}}


def visible_output(raw, *, last=False, bound=1024):
    portion = raw[-bound:] if last else raw[:bound]
    try: text = portion.decode('utf-8'); valid = True
    except UnicodeError: text = portion.decode('utf-8', errors='replace'); valid = False
    return {'text': text, 'utf8_valid': valid, 'truncated': len(raw) > bound, 'original_bytes': len(raw)}


def project(public, stored, arm, acquisition=None):
    if arm not in ARMS: raise ValueError('Unknown ablation arm')
    feedback = current_feedback(public, stored)
    if feedback['passed']: raise ValueError('Recovery requires a public failure')
    rendered = []
    for row in feedback['cases']:
        o = row['observed']
        rendered.append({'id': row['id'], 'passed': row['passed'], 'status': o['status'], 'returncode': o['returncode'],
                         'stdout': visible_output(base64.b64decode(o['stdout_b64'])),
                         'stderr': visible_output(normalized_stderr(o), last=True)})
    payload = {k: public[k] for k in ('instruction', 'files', 'comparator', 'public_cases')}
    payload['latest_feedback'] = {'passed': False, 'passed_cases': feedback['passed_cases'],
                                  'total_cases': feedback['total_cases'], 'cases': rendered}
    if arm != 'feedback':
        table = {'available': False, 'reason': 'not_acquired', 'locations': None}
        if acquisition is not None:
            diagnostic = analyze(public, stored, acquisition)
            table['reason'] = 'incomplete_or_inconsistent_coverage'
            if diagnostic['available']:
                table = {'available': True, 'reason': None, 'locations': diagnostic['locations']}
                if arm == 'neutral':
                    table['locations'] = [{**{k:r[k] for k in ('file', 'line', 'source')},
                                           **{k:'not supplied' for k in ('failing_covered', 'passing_covered', 'squared_ochiai')}}
                                          for r in table['locations']]
        payload['source_excerpts'] = table
    return {'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': canonical(payload)}],
            'provider_call_enabled': False, 'mode': 'offline_stdin_ablation_preparation'}


def triplet(public, stored, acquisition):
    requests = {a: project(public, stored, a, acquisition) for a in ARMS}
    payloads = {a: json.loads(r['messages'][1]['content']) for a,r in requests.items()}
    for a in ('neutral', 'scored'):
        if {k:v for k,v in payloads[a].items() if k != 'source_excerpts'} != payloads['feedback']:
            raise ValueError('Shared solver information differs')
    n, s = (payloads[a]['source_excerpts'] for a in ('neutral', 'scored'))
    if any(n[k] != s[k] for k in ('available', 'reason')): raise ValueError('Excerpt availability differs')
    if n['locations'] is not None:
        core = lambda rows: [{k:r[k] for k in ('file', 'line', 'source')} for r in rows]
        if core(n['locations']) != core(s['locations']): raise ValueError('Excerpt location/order/content differs')
    return requests
