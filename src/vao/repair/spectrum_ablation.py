"""Inert public-only F/N/S projections for a prospective information ablation.

No task selection, model client, scorer/evaluator channel or live launch exists
here. Validate current public feedback, recompute coverage scores from public
observations and erase all outcome associations in the neutral excerpt arm.
"""
from __future__ import annotations

import json

from .diagnostics import binding, validate_public
from .environment import REPAIR_SYSTEM, canonical
from .spectra import analyze_spectrum, score

ARMS = ('feedback', 'neutral', 'scored')
SYSTEM = REPAIR_SYSTEM + (
    ' In this experiment the supplied feedback and any coverage describe the exact current files.'
    ' Source excerpts, when available, list all covered locations in filename/line order.'
    ' Test associations may be withheld. A withheld value is not zero.'
    ' Squared Ochiai describes association with failing tests, not fault probability.'
    ' Equal values are ties; missing behavior may never execute.'
    ' Preserve all required behavior, including cases that already pass.'
)


def current_feedback(public, stored):
    """Reject stale or inconsistent feedback before projecting any arm."""
    validate_public(public, public['files'])
    if stored['binding'] != binding(public, public['files']):
        raise ValueError('Feedback does not bind the current public state')
    data = stored['feedback']
    if set(data) != {'passed', 'passed_cases', 'total_cases', 'cases'}:
        raise ValueError('Only complete public feedback is accepted')
    cases = public['public_cases']
    rows = data['cases']
    if [r['id'] for r in rows] != [c['id'] for c in cases]:
        raise ValueError('Public case identities/order differ')
    for case, row in zip(cases, rows):
        if set(row) != {'id', 'passed', 'observed'} or type(row['passed']) is not bool:
            raise ValueError('Unknown or invalid public feedback fields')
        observation = row['observed']
        allowed = {'returned': {'status', 'value'}, 'exception': {'status', 'exception'},
                   'load_error': {'status', 'exception'}, 'timeout': {'status'},
                   'output_limit': {'status'}, 'non_json_output': {'status'},
                   'invalid_output': {'status'}, 'worker_exit': {'status', 'returncode'}}
        # Outcomes unsupported by this projection must be handled explicitly,
        # never copied as arbitrary nested metadata into a solver prompt.
        if not isinstance(observation, dict) or set(observation) != allowed.get(observation.get('status')):
            raise ValueError('Unsupported public observation schema')
        if row['passed'] != score(case, observation):
            raise ValueError('Public labels contradict public expectations')
    if (type(data['passed']) is not bool or type(data['passed_cases']) is not int
            or type(data['total_cases']) is not int or data['total_cases'] != len(cases)
            or data['passed_cases'] != sum(r['passed'] for r in rows)
            or data['passed'] != all(r['passed'] for r in rows)):
        raise ValueError('Public feedback aggregates differ')
    return json.loads(canonical(data))


def excerpt_table(public, stored, acquisition):
    """Derive scores, never trust cached rankings or select a favorable top-k."""
    feedback = current_feedback(public, stored)
    if feedback['passed']:
        raise ValueError('Recovery requires a public-failing checkpoint')
    if acquisition is None:
        return {'available': False, 'reason': 'not_acquired', 'locations': None}
    if acquisition['binding'] != stored['binding']:
        raise ValueError('Coverage belongs to different current files or tests')
    if [r['id'] for r in acquisition['cases']] != [r['id'] for r in feedback['cases']]:
        raise ValueError('Coverage and feedback case identities differ')
    for row, old in zip(acquisition['cases'], feedback['cases']):
        if row['stored_observed'] != old['observed'] or row['stored_passed'] != old['passed']:
            raise ValueError('Coverage does not retain the supplied feedback')
    diagnostic = analyze_spectrum(public, acquisition)
    if not diagnostic['available']:
        # Both controls expose the same generic availability flag. Do not leak
        # per-case association, timing or quality summaries via neutral metadata.
        return {'available': False, 'reason': 'incomplete_or_inconsistent_coverage', 'locations': None}
    locations = []
    for group in diagnostic['ranking']:
        for location in group['locations']:
            filename, line = location['file'], location['line']
            locations.append({'file': filename, 'line': line,
                'source': public['files'][filename].splitlines()[line - 1],
                'failing_covered': location['failing_covered'],
                'passing_covered': location['passing_covered'],
                'squared_ochiai': group['squared_exact']})
    return {'available': True, 'reason': None,
            'locations': sorted(locations, key=lambda row: (row['file'], row['line']))}


def project(public, stored, arm, acquisition=None):
    """Return an offline request; it cannot be passed as a live authorization."""
    if arm not in ARMS:
        raise ValueError('Unknown ablation arm')
    feedback = current_feedback(public, stored)
    if feedback['passed']:
        raise ValueError('Recovery requires a public-failing checkpoint')
    payload = {k: public[k] for k in ('instruction', 'entrypoint', 'files', 'public_cases')}
    payload['latest_feedback'] = feedback
    if arm != 'feedback':
        table = excerpt_table(public, stored, acquisition)
        if arm == 'neutral' and table['locations'] is not None:
            table['locations'] = [{**{k: row[k] for k in ('file', 'line', 'source')},
                                  'failing_covered': 'not supplied',
                                  'passing_covered': 'not supplied',
                                  'squared_ochiai': 'not supplied'} for row in table['locations']]
        payload['source_excerpts'] = table
    return {'messages': [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': canonical(payload)}],
            'mode': 'offline_spectrum_ablation_preparation', 'provider_call_enabled': False}


def triplet(public, stored, acquisition):
    """Build all arms together, guarding the intended controlled difference."""
    requests = {arm: project(public, stored, arm, acquisition) for arm in ARMS}
    payloads = {arm: json.loads(request['messages'][1]['content']) for arm, request in requests.items()}
    for arm in ('neutral', 'scored'):
        shared = {k: v for k, v in payloads[arm].items() if k != 'source_excerpts'}
        if shared != payloads['feedback']:
            raise ValueError('Shared solver information differs')
    neutral, scored = (payloads[a]['source_excerpts'] for a in ('neutral', 'scored'))
    if any(neutral[k] != scored[k] for k in ('available', 'reason')):
        raise ValueError('Availability differs between excerpt arms')
    if neutral['locations'] is not None:
        def core(rows):
            return [{k: row[k] for k in ('file', 'line', 'source')} for row in rows]
        if core(neutral['locations']) != core(scored['locations']):
            raise ValueError('Excerpt locations, order or source differ')
    return requests
