"""Review response contracts without real transport or evaluator leakage."""
from copy import deepcopy
import json

import pytest

from vao.repair.contracts import CONTRACTS, construct, decode, demo, validate
from vao.repair.environment import RepairTask, canonical, identity


class Verifier:
    def preflight(self):
        return {'test_double': True}

    def check(self, files, entrypoint, cases):
        good = files['solution.py'] == 'def solve(x):\n    return x + 1\n'
        return {'passed': good, 'passed_cases': int(good), 'total_cases': 1,
                'cases': [{'id': cases[0]['id'], 'passed': good, 'observed': {'status': 'returned', 'value': 0}}],
                'verifier_seconds': .01}


def tasks(n=2):
    return [RepairTask.from_dicts({'schema_version': 1, 'task_id': f'development/test-{i}',
            'instruction': 'Repair solve', 'entrypoint': {'module': 'solution', 'function': 'solve'},
            'files': {'solution.py': 'def solve(x):\n    return x\n'},
            'public_cases': [{'id': 'public', 'args': [1], 'expected': 2}],
            'provenance': {'kind': 'synthetic_engineering_fixture'}},
            {'cases': [{'id': 'EVALUATOR_SECRET_CANARY', 'args': [100], 'expected': 101}]}) for i in range(n)]


def rehash(plan):
    plan['packet_id'] = identity({k: v for k, v in plan.items() if k != 'packet_id'})
    return plan


def test_matched_inputs_seeds_budget_and_private_boundary():
    plan = construct(tasks(), Verifier())
    assert validate(plan)['requests'] == 6 and plan['api_calls'] == 0
    assert plan['monetary_authorization_usd'] is None and not plan['live_calls_enabled']
    for index in range(2):
        rows = [r for r in plan['requests'] if r['metadata']['task_index'] == index]
        assert len({r['provider_body']['seed'] for r in rows}) == 1
        assert len({r['provider_body']['messages'][1]['content'] for r in rows}) == 1
        assert len({r['request']['remaining_budget_usd'] for r in rows}) == 1
    for row in plan['requests']:
        assert 'EVALUATOR_SECRET_CANARY' not in canonical(row['provider_body'])
        assert 'verifier_seconds' not in canonical(row['provider_body'])
        assert ('response_format' in row['provider_body']) == (row['metadata']['contract'] != 'python_text')


def test_order_balances_three_contract_positions_across_twelve_tasks():
    plan = construct(tasks(12), Verifier())
    for slot in range(3):
        order = [plan['requests'][i]['metadata']['contract'] for i in range(slot, 36, 3)]
        assert all(order.count(c) == 4 for c in CONTRACTS)
    assert plan['maximum_calls'] == 36
    assert plan['maximum_new_reservations_usd'] == '0.05455872'
    assert plan['maximum_cumulative_commitment_usd'] == '0.06467283'


def test_empty_objects_and_python_syntax_do_not_imply_a_callable_solution():
    task = tasks(1)[0]
    assert not decode(task, '{}', 'stop', 'json_current')['artifact_valid']
    parsed = decode(task, '{}', 'stop', 'python_text')
    assert parsed['artifact_valid'] and parsed['syntax_valid'] and not parsed['declared_entrypoint']
    assert not decode(task, '```python\ndef solve(x): return x\n```', 'stop', 'python_text')['syntax_valid']
    for contract in CONTRACTS:
        assert not decode(task, 'anything', 'length', contract)['artifact_valid']


def test_decoder_has_no_execution_side_effects(tmp_path):
    sentinel = tmp_path / 'must-not-exist'
    source = f"open({str(sentinel)!r}, 'w').write('bad')\ndef solve(x): return x\n"
    decoded = decode(tasks(1)[0], source, 'stop', 'python_text')
    assert decoded['syntax_valid'] and decoded['declared_entrypoint']
    assert not sentinel.exists()


def test_projection_and_authorization_tampering_are_rejected_even_after_rehash():
    plan = construct(tasks(), Verifier())
    bad = deepcopy(plan)
    bad['requests'][0]['provider_body']['messages'][1]['content'] += ' EVALUATOR_SECRET_CANARY'
    with pytest.raises(ValueError, match='projection'):
        validate(rehash(bad))
    bad = deepcopy(plan)
    bad['live_calls_enabled'] = True
    with pytest.raises(ValueError, match='authorization'):
        validate(rehash(bad))
    bad = deepcopy(plan)
    bad['requests'].pop()
    with pytest.raises(ValueError, match='Missing'):
        validate(rehash(bad))


def test_scripted_demo_is_explicitly_not_model_evidence(tmp_path):
    plan = construct(tasks(), Verifier())
    output = tmp_path / 'demo'
    result = demo(plan, output, Verifier())
    assert result['api_calls'] == 0 and not result['model_results']
    saved = json.loads((output / 'demo.json').read_text())
    assert len(saved['observations']) == 6
    assert all(not row['full_pass'] for row in saved['observations'])
    with pytest.raises(FileExistsError):
        demo(plan, output, Verifier())


def test_already_solved_initial_bug_is_not_silently_removed():
    class AlwaysPass(Verifier):
        def check(self, *args):
            result = super().check(*args)
            result['passed'] = True
            return result
    with pytest.raises(ValueError, match='initially failing'):
        construct(tasks(), AlwaysPass())


def test_sampling_and_proposed_budget_drift_are_rejected():
    plan = construct(tasks(), Verifier())
    for field, value in [('temperature', .3), ('max_tokens', 2048)]:
        bad = deepcopy(plan)
        bad['provider_settings'][field] = value
        with pytest.raises(ValueError, match='settings'):
            validate(rehash(bad))
    bad = deepcopy(plan)
    bad['proposed_cap_usd'] = '1.00'
    with pytest.raises(ValueError, match='cap differs'):
        validate(rehash(bad))
    bad = deepcopy(plan)
    bad['requests'].reverse()
    with pytest.raises(ValueError, match='order differs'):
        validate(rehash(bad))
