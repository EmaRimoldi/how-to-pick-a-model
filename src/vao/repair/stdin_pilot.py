"""Prospective stdin pilot planning and finite-panel analysis; no provider calls.

Normalized outcomes are produced only after receipt/projection/native-test audit.
This module neither collects responses nor promotes itself into a funded freeze.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import json

from .environment import identity
from .stdin_ablation import ARMS, binding

MODEL = 'google/gemma-3-4b-it'
INPUT_RESERVATION = 65536
OUTPUT_LIMIT = 4096
PRIOR_COMMITMENT = Decimal('0.25463059')
PROPOSED_ALLOCATION = Decimal('0.32')
CUMULATIVE_CAP = Decimal('0.60')
PER_CALL_RESERVATION = (INPUT_RESERVATION * Decimal('0.04') + OUTPUT_LIMIT * Decimal('0.05')) / 1_000_000
DRAW_COUNT = 3
GROUP_COUNT = 11


def parse_artifact(text):
    """No best-effort extraction or repair of model output, including duplicate keys."""
    def pairs(values):
        result = {}
        for k, v in values:
            if k in result:
                raise ValueError('Duplicate JSON field')
            result[k] = v
        return result

    try:
        if not isinstance(text, str):
            return None
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        if (not isinstance(value, dict) or set(value) != {'main.py'}
                or not isinstance(value['main.py'], str)
                or not 0 < len(value['main.py'].encode('utf-8')) <= 262144):
            return None
    except (ValueError, UnicodeError, RecursionError):
        return None
    # Python syntax is intentionally not an admission rule: valid JSON can
    # materialize a syntax-error checkpoint which must remain in the flow.
    return value


def plan(tasks, qualification_decisions, archive_sha256):
    if (len(tasks) != GROUP_COUNT or len(qualification_decisions) != 12
            or [(g['problem_id'], g['selected_pair_index']) for g in qualification_decisions
                if g['selected_pair_index'] is not None] != [(t['problem_id'], t['pair_index']) for t in tasks]):
        raise ValueError('Keep all prospectively qualified groups and original decisions')
    if len({t['problem_id'] for t in tasks}) != GROUP_COUNT:
        raise ValueError('Duplicate problem group')
    if not isinstance(archive_sha256, str) or len(archive_sha256) != 64 or any(c not in '0123456789abcdef' for c in archive_sha256):
        raise ValueError('Source evidence SHA-256 required')
    roster, slots = [], []
    for task in tasks:
        bound = binding(task['public'])
        if bound != task['binding']:
            raise ValueError('Source public binding differs')
        roster.append({'problem_id': task['problem_id'], 'pair_index': task['pair_index'],
                       'original_public_binding': bound})
        key = identity({'study': 'stdin-diagnostic-pilot-v1', 'seed': 20261030, 'source': bound, 'phase': 'initial'})
        slots.append({'id': key, 'problem_id': task['problem_id'], 'phase': 'initial',
                      'arm': 'feedback', 'draw': None, 'seed': int(key[:8], 16) % (2**31)})
    for draw in range(DRAW_COUNT):
        for i, task in enumerate(tasks):
            # Every arm occupies each within-task order position once over draws.
            offset = (i + draw) % len(ARMS)
            order = ARMS[offset:] + ARMS[:offset]
            paired = identity({'study': 'stdin-diagnostic-pilot-v1', 'seed': 20261030,
                               'source': task['binding'], 'phase': 'recovery', 'draw': draw})
            for arm in order:
                slots.append({'id': identity({'paired': paired, 'arm': arm}),
                              'problem_id': task['problem_id'], 'phase': 'recovery',
                              'arm': arm, 'draw': draw, 'seed': int(paired[:8], 16) % (2**31)})
    maximum = len(slots) * PER_CALL_RESERVATION
    if maximum > PROPOSED_ALLOCATION or PRIOR_COMMITMENT + PROPOSED_ALLOCATION > CUMULATIVE_CAP:
        raise ValueError('Proposed allocation exceeds standing ceiling')
    return {'schema_version': 1, 'kind': 'numerical_design_not_live_freeze', 'provider_call_enabled': False,
            'source_evidence_sha256': archive_sha256, 'roster': roster,
            'all_original_group_decisions': qualification_decisions, 'slots': slots,
            'solver': {'model': MODEL, 'endpoint': 'parasail/bf16', 'quantization': 'bf16',
                       'temperature': 0.7, 'seed': 20261030, 'input_reservation': INPUT_RESERVATION,
                       'output_limit': OUTPUT_LIMIT, 'fallbacks': False, 'minimum_admission_spacing_seconds': 60},
            'budget': {'prior_committed_usd': str(PRIOR_COMMITMENT), 'unresolved_historical_reserves': 14,
                       'per_call_reservation_usd': str(PER_CALL_RESERVATION), 'maximum_calls': len(slots),
                       'maximum_all_reservations_usd': str(maximum), 'proposed_allocation_usd': str(PROPOSED_ALLOCATION),
                       'cumulative_cap_usd': str(CUMULATIVE_CAP), 'new_explicit_human_allocation': False},
            'criteria': {'minimum_generated_failures': 6, 'minimum_repeated_scored_repairs': 3,
                         'repeated_repair_draws': 2, 'minimum_primary_gain': [1, 10],
                         'primary': ['scored', 'neutral'], 'safety': ['scored', 'feedback'],
                         'positive_primary_each_draw': True, 'nonnegative_safety_each_draw': True,
                         'complete_audited_bank_required': True}}


def validate_panel(roster, rows):
    expected = [r['problem_id'] for r in roster]
    if len(expected) != GROUP_COUNT or len(set(expected)) != GROUP_COUNT or len(rows) != GROUP_COUNT:
        raise ValueError('Eleven unique selected groups required')
    if [r.get('problem_id') for r in rows] != expected:
        raise ValueError('Do not drop or reorder selected groups')
    for row in rows:
        if set(row) != {'problem_id', 'initial', 'recovery'}:
            raise ValueError('Unexpected panel fields')
        initial = row['initial']
        if not isinstance(initial, dict) or set(initial) != {'status', 'full_repair'}:
            raise ValueError('Expected explicit initial status and evaluator outcome')
        status, success = initial['status'], initial['full_repair']
        if status not in {'missing', 'invalid', 'public_pass', 'public_fail'}:
            raise ValueError('Unknown initial state')
        if (status == 'missing' and success is not None
                or status != 'missing' and type(success) is not bool
                or status in {'invalid', 'public_fail'} and success is not False):
            raise ValueError('Initial outcome inconsistent with status')
        recovery = row['recovery']
        if not isinstance(recovery, dict) or set(recovery) != set(ARMS):
            raise ValueError('All three recovery conditions must remain')
        for outcomes in recovery.values():
            if not isinstance(outcomes, list) or len(outcomes) != DRAW_COUNT:
                raise ValueError('Every selected draw must remain')
            if any(value is not None and type(value) is not bool for value in outcomes):
                raise ValueError('Outcome must be Boolean or explicit missing')
            if status != 'public_fail' and any(value is not None for value in outcomes):
                raise ValueError('Recovery may not follow private failures or unmaterialized sources')


def bounds(a, b):
    n = len(a)
    return [float(Fraction(sum(v is True for v in a) - sum(v is True for v in b) - b.count(None), n)),
            float(Fraction(sum(v is True for v in a) + a.count(None) - sum(v is True for v in b), n))]


def analyze(roster, rows, *, evidence_audited):
    if type(evidence_audited) is not bool:
        raise ValueError('Explicit terminal evidence audit state required')
    validate_panel(roster, rows)
    eligible = [r for r in rows if r['initial']['status'] == 'public_fail']
    flow = {s: sum(r['initial']['status'] == s for r in rows)
            for s in ('missing', 'invalid', 'public_pass', 'public_fail')}
    end_to_end = {arm: [] for arm in ARMS}
    for row in rows:
        for arm in ARMS:
            end_to_end[arm].extend(row['recovery'][arm] if row['initial']['status'] == 'public_fail'
                                   else [row['initial']['full_repair']] * DRAW_COUNT)
    known = flow['missing'] == 0 and all(v is not None for values in end_to_end.values() for v in values)
    complete = known and evidence_audited
    result = {'selected_groups': GROUP_COUNT, 'initial_flow': flow,
              'initial_full_repairs': sum(r['initial']['full_repair'] is True for r in rows),
              'initial_false_acceptances': sum(r['initial']['status'] == 'public_pass' and not r['initial']['full_repair'] for r in rows),
              'known_eligible_generated_checkpoints': len(eligible), 'eligible_count_complete': flow['missing'] == 0,
              'known_outcomes_complete': known, 'evidence_audited': evidence_audited,
              'conditional_means': None, 'conditional_contrasts': None, 'repeatability': None,
              'end_to_end_selected_bounds': {f'scored_minus_{other}': bounds(end_to_end['scored'], end_to_end[other])
                                            for other in ('neutral', 'feedback')},
              'gate': 'inconclusive', 'selector_training_allowed': False,
              'independent_replication_planning_allowed': False}
    if not complete:
        return result
    m = len(eligible)
    if not m:
        result['gate'] = 'insufficient_generated_failures'
        return result
    totals = {arm: [sum(r['recovery'][arm][d] for r in eligible) for d in range(DRAW_COUNT)] for arm in ARMS}
    means = {arm: Fraction(sum(t), m*DRAW_COUNT) for arm, t in totals.items()}
    primary = [a-b for a,b in zip(totals['scored'], totals['neutral'])]
    safety = [a-b for a,b in zip(totals['scored'], totals['feedback'])]
    repeated = sum(sum(r['recovery']['scored']) >= 2 for r in eligible)
    conditions = {'at_least_six_generated_failures': m >= 6,
                  'three_repeated_scored_repairs': repeated >= 3,
                  'positive_primary_every_draw': all(v > 0 for v in primary),
                  'primary_gain_at_least_ten_points': means['scored'] - means['neutral'] >= Fraction(1, 10),
                  'nonnegative_safety_every_draw': all(v >= 0 for v in safety)}
    passed = all(conditions.values())
    result.update({'conditional_means': {arm: float(v) for arm, v in means.items()},
                   'conditional_contrasts': {f'scored_minus_{other}': float(means['scored']-means[other])
                                             for other in ('neutral', 'feedback')},
                   'repeatability': {'success_counts_by_draw': totals, 'primary_net_by_draw': primary,
                                     'safety_net_by_draw': safety, 'repeated_scored_checkpoints': repeated,
                                     'criteria': conditions},
                   'gate': 'advance_to_replication_planning' if passed else 'insufficient_generated_failures' if m < 6 else 'does_not_advance',
                   'independent_replication_planning_allowed': passed})
    return result
