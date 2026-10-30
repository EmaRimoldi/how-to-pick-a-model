import copy
import json
from decimal import Decimal

import pytest

from vao.repair.stdin_ablation import ARMS, binding
from vao.repair.stdin_pilot import analyze, parse_artifact, plan


def design():
    tasks, decisions = [], []
    for i in range(11):
        public = {'schema_version': 3, 'instruction': f'Print {i}.', 'files': {'main.py': 'print(-1)\n'},
                  'comparator': 'ascii_whitespace_tokens',
                  'public_cases': [{'id': 'case_001', 'stdin': '', 'expected_stdout': str(i)}]}
        tasks.append({'problem_id': f'problem{i}', 'pair_index': 0, 'binding': binding(public), 'public': public})
        decisions.append({'problem_id': f'problem{i}', 'selected_pair_index': 0})
    decisions.append({'problem_id': 'excluded', 'selected_pair_index': None})
    return tasks, decisions


def panel():
    tasks, _ = design()
    rows = [{'problem_id': t['problem_id'], 'initial': {'status': 'public_fail', 'full_repair': False},
             'recovery': {a: [False]*3 for a in ARMS}} for t in tasks]
    return tasks, rows


def test_plan_preserves_population_and_balances_order_without_enabling_calls():
    tasks, decisions = design(); p = plan(tasks, decisions, 'a'*64)
    assert p['provider_call_enabled'] is False
    assert len(p['slots']) == len({s['id'] for s in p['slots']}) == 110
    assert p['all_original_group_decisions'] == decisions
    assert all(s['phase'] == 'initial' for s in p['slots'][:11])
    assert all(s['phase'] == 'recovery' for s in p['slots'][11:])
    for task in tasks:
        orders = []
        for d in range(3):
            slots = [s for s in p['slots'] if s['problem_id'] == task['problem_id'] and s['draw'] == d]
            assert len({s['seed'] for s in slots}) == 1
            orders.append([s['arm'] for s in slots])
        assert all(set(order[i] for order in orders) == set(ARMS) for i in range(3))
    b = p['budget']
    assert Decimal(b['maximum_all_reservations_usd']) == Decimal('0.31088640')
    assert Decimal(b['prior_committed_usd']) + Decimal(b['proposed_allocation_usd']) < Decimal('0.60')
    tasks.pop()
    with pytest.raises(ValueError):
        plan(tasks, decisions, 'a'*64)


@pytest.mark.parametrize('bad', ['```json\n{"main.py":"print(1)"}\n```',
    '{"main.py":"a", "main.py":"b"}', '{"main.py":"x","private":"secret"}',
    '{"main.py":null}', '{"main.py":""}', '{"main.py":NaN}', '{"main.py":"\\ud800"}',
    'Here is the code: print(1)', '[]'])
def test_parser_never_repairs_or_extracts_a_response(bad):
    assert parse_artifact(bad) is None


def test_json_syntax_error_source_is_a_materializable_checkpoint():
    assert parse_artifact(json.dumps({'main.py': 'if:\n'})) == {'main.py': 'if:\n'}
    assert parse_artifact(json.dumps({'main.py': 'x'*262145})) is None


def test_repeatable_positive_only_allows_replication_not_training():
    roster, rows = panel()
    for r in rows[:3]:
        r['recovery']['scored'] = [True]*3
    a = analyze(roster, rows, evidence_audited=True)
    assert a['gate'] == 'advance_to_replication_planning'
    assert a['repeatability']['primary_net_by_draw'] == [3, 3, 3]
    assert a['selector_training_allowed'] is False
    assert a['conditional_contrasts']['scored_minus_neutral'] == pytest.approx(3/11)
    assert a['end_to_end_selected_bounds']['scored_minus_neutral'] == [3/11, 3/11]


def test_null_and_favorable_secondary_cannot_replace_primary():
    roster, rows = panel()
    assert analyze(roster, rows, evidence_audited=True)['gate'] == 'does_not_advance'
    for r in rows[:3]:
        r['recovery']['scored'] = [True]*3
        r['recovery']['neutral'] = [True]*3
    a = analyze(roster, rows, evidence_audited=True)
    assert a['conditional_contrasts']['scored_minus_feedback'] > 0
    assert a['conditional_contrasts']['scored_minus_neutral'] == 0
    assert a['gate'] == 'does_not_advance'


def test_aggregate_gain_cannot_override_bad_draw_or_feedback_regression():
    roster, rows = panel()
    for r in rows[:3]:
        r['recovery']['scored'] = [False, True, True]
    a = analyze(roster, rows, evidence_audited=True)
    assert a['conditional_contrasts']['scored_minus_neutral'] > .10
    assert a['gate'] == 'does_not_advance'
    for r in rows:
        r['recovery']['feedback'] = [True]*3
    for r in rows[:3]:
        r['recovery']['scored'] = [True]*3
    assert analyze(roster, rows, evidence_audited=True)['gate'] == 'does_not_advance'


@pytest.mark.parametrize('kind', ['missing_initial', 'missing_recovery', 'unaudited'])
def test_incomplete_banks_do_not_publish_conditional_means_or_pass_gate(kind):
    roster, rows = panel()
    for r in rows:
        r['recovery']['scored'] = [True]*3
    if kind == 'missing_initial':
        rows[0]['initial'] = {'status': 'missing', 'full_repair': None}
        rows[0]['recovery'] = {a: [None]*3 for a in ARMS}
    elif kind == 'missing_recovery':
        rows[0]['recovery']['neutral'][1] = None
    a = analyze(roster, rows, evidence_audited=kind != 'unaudited')
    assert a['gate'] == 'inconclusive' and a['conditional_means'] is None
    assert a['conditional_contrasts'] is None and a['repeatability'] is None
    low, high = a['end_to_end_selected_bounds']['scored_minus_neutral']
    assert -1 <= low <= high <= 1


def test_initial_false_acceptance_is_failure_and_cannot_trigger_recovery():
    roster, rows = panel()
    for r in rows[:6]:
        r['initial'] = {'status': 'public_pass', 'full_repair': False}
        r['recovery'] = {a: [None]*3 for a in ARMS}
    for r in rows[6:]:
        r['recovery']['scored'] = [True]*3
    a = analyze(roster, rows, evidence_audited=True)
    assert a['initial_false_acceptances'] == 6
    assert a['gate'] == 'insufficient_generated_failures'
    assert a['conditional_means']['scored'] == 1
    assert a['end_to_end_selected_bounds']['scored_minus_neutral'] == [5/11, 5/11]
    rows[0]['recovery']['scored'][0] = True
    with pytest.raises(ValueError):
        analyze(roster, rows, evidence_audited=True)


def test_missing_and_invalid_initial_are_not_interchangeable_or_droppable():
    roster, rows = panel()
    for r in rows:
        r['initial'] = {'status': 'invalid', 'full_repair': False}
        r['recovery'] = {a: [None]*3 for a in ARMS}
    a = analyze(roster, rows, evidence_audited=True)
    assert a['known_outcomes_complete'] and a['gate'] == 'insufficient_generated_failures'
    assert a['end_to_end_selected_bounds']['scored_minus_neutral'] == [0, 0]
    with pytest.raises(ValueError):
        analyze(roster, rows[:-1], evidence_audited=True)
    bad = copy.deepcopy(rows); bad[0]['initial']['status'] = 'missing'
    with pytest.raises(ValueError):
        analyze(roster, bad, evidence_audited=True)
