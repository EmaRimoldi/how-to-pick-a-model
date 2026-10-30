"""Public-only package coverage and inert F/N/S inputs; no model dispatch."""
import json
import math
import time

from .environment import canonical, identity
from .package_environment import validate_public
from .spectra import analyze_bound_spectrum
from .spectrum_ablation import ARMS, SYSTEM, validate_feedback

PACKAGE_SYSTEM = SYSTEM + ' The support_files are visible immutable context. Replace only the filenames in files.'


def binding(public):
    validate_public(public)
    return identity({k: public[k] for k in ('schema_version', 'instruction', 'entrypoint',
                                          'files', 'support_files', 'public_cases')})


def current_feedback(public, stored):
    if stored['binding'] != binding(public):
        raise ValueError('Package feedback does not match current sources or cases')
    return validate_feedback(public['public_cases'], stored['feedback'])


def validate_verifier_context(public, verifier):
    bound = verifier.public
    if (public['support_files'] != bound['support_files']
            or public['entrypoint'] != bound['entrypoint']
            or set(public['files']) != set(bound['files'])):
        raise ValueError('Verifier immutable context differs from the bound public state')


def observe(public, verifier):
    validate_public(public)
    validate_verifier_context(public, verifier)
    result = verifier.check(public['files'], public['entrypoint'], public['public_cases'])
    return {'binding': binding(public),
            'feedback': {k: result[k] for k in ('passed', 'passed_cases', 'total_cases', 'cases')},
            'verifier_seconds': result['verifier_seconds']}


def acquire(public, stored, verifier):
    feedback = current_feedback(public, stored)
    validate_verifier_context(public, verifier)
    if feedback['passed']:
        raise ValueError('Diagnostic acquisition requires a public failure')
    start = time.monotonic()
    rows = []
    for case, previous in zip(public['public_cases'], feedback['cases'], strict=True):
        normal = verifier.invoke(public['files'], public['entrypoint'], case)
        coverage = verifier.coverage(public['files'], public['entrypoint'], case)
        rows.append({'id': case['id'], 'ordinary': normal, 'coverage_result': coverage,
                     'stored_observed': previous['observed'], 'stored_passed': previous['passed']})
    return {'binding': stored['binding'], 'cases': rows, 'additional_executions': 2 * len(rows),
            'seconds': time.monotonic() - start}


def analyze(public, stored, acquisition):
    feedback = current_feedback(public, stored)
    if (type(acquisition['additional_executions']) is not int
            or acquisition['additional_executions'] != 2 * len(public['public_cases'])
            or type(acquisition['seconds']) not in (int, float)
            or not math.isfinite(acquisition['seconds']) or acquisition['seconds'] < 0):
        raise ValueError('Invalid package acquisition resource accounting')
    if [r['id'] for r in acquisition['cases']] != [r['id'] for r in feedback['cases']]:
        raise ValueError('Package acquisition omitted or reordered cases')
    for row, old in zip(acquisition['cases'], feedback['cases'], strict=True):
        if row['stored_observed'] != old['observed'] or row['stored_passed'] != old['passed']:
            raise ValueError('Package acquisition refers to different saved feedback')
    files = validate_public(public)
    return analyze_bound_spectrum(files, public['public_cases'], acquisition, binding(public))


def project(public, stored, arm, acquisition=None):
    if arm not in ARMS:
        raise ValueError('Unknown package ablation arm')
    feedback = current_feedback(public, stored)
    if feedback['passed']:
        raise ValueError('Recovery requires a public failure')
    files = validate_public(public)
    payload = {k: public[k] for k in ('instruction', 'entrypoint', 'files', 'support_files', 'public_cases')}
    payload['latest_feedback'] = feedback
    if arm != 'feedback':
        table = {'available': False, 'reason': 'not_acquired', 'locations': None}
        if acquisition is not None:
            diagnostic = analyze(public, stored, acquisition)
            if not diagnostic['available']:
                table['reason'] = 'incomplete_or_inconsistent_coverage'
            else:
                rows = []
                for group in diagnostic['ranking']:
                    for loc in group['locations']:
                        rows.append({'file': loc['file'], 'line': loc['line'],
                                     'source': files[loc['file']].splitlines()[loc['line'] - 1],
                                     'editable': loc['file'] in public['files'],
                                     'failing_covered': loc['failing_covered'] if arm == 'scored' else 'not supplied',
                                     'passing_covered': loc['passing_covered'] if arm == 'scored' else 'not supplied',
                                     'squared_ochiai': group['squared_exact'] if arm == 'scored' else 'not supplied'})
                table = {'available': True, 'reason': None,
                         'locations': sorted(rows, key=lambda r: (r['file'], r['line']))}
        payload['source_excerpts'] = table
    return {'messages': [{'role': 'system', 'content': PACKAGE_SYSTEM},
                         {'role': 'user', 'content': canonical(payload)}],
            'provider_call_enabled': False, 'mode': 'offline_package_ablation_preparation'}


def triplet(public, stored, acquisition):
    requests = {a: project(public, stored, a, acquisition) for a in ARMS}
    payloads = {a: json.loads(r['messages'][1]['content']) for a, r in requests.items()}
    for a in ('neutral', 'scored'):
        if {k: v for k, v in payloads[a].items() if k != 'source_excerpts'} != payloads['feedback']:
            raise ValueError('Package arm information differs')
    neutral, scored = (payloads[a]['source_excerpts'] for a in ('neutral', 'scored'))
    if any(neutral[k] != scored[k] for k in ('available', 'reason')):
        raise ValueError('Package acquisition availability differs')
    if neutral['locations'] is not None:
        fields = ('file', 'line', 'source', 'editable')
        if ([{k: r[k] for k in fields} for r in neutral['locations']]
                != [{k: r[k] for k in fields} for r in scored['locations']]):
            raise ValueError('Package excerpt content/order differs')
    return requests
