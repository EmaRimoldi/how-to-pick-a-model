"""Independent checks of missingness, bug weighting and public-only selection."""
import json
from decimal import Decimal

import pytest

from vao.analysis.repair_calibration import analyze, descriptive_interval, group_estimate, render
from vao.repair.environment import RepairTask
from vao.repair.pilot import Design, ScriptedTransport, collect


class Verifier:
    def preflight(self):
        return {"test_double": True}

    def check(self, files, entrypoint, cases):
        passed = files['solution.py'] == 'fixed' or (files['solution.py'] == 'overfit' and cases[0]['id'] == 'public')
        return {"passed": passed, "passed_cases": int(passed), "total_cases": 1,
                "cases": [{"id": cases[0]['id'], "passed": passed, "observed": {"status": "returned", "value": 0}}],
                "verifier_seconds": .01}


def task(name):
    return RepairTask.from_dicts({"schema_version": 1, "task_id": name,
        "instruction": "Repair solve", "entrypoint": {"module": "solution", "function": "solve"},
        "files": {"solution.py": "original"}, "public_cases": [{"id": "public", "args": [1], "expected": 1}],
        "provenance": {"kind": "synthetic_engineering_fixture"}},
        {"cases": [{"id": "private", "args": [2], "expected": 2}]})


def make_bank(tmp_path, responder, *, tasks=None, **accounting):
    output = tmp_path / 'bank'
    collect(tasks or [task('synthetic/one')], Design(1, 2, 2), output, Verifier(),
            lambda out: ScriptedTransport(out, responder, **accounting))
    return output


def repairs(request, meta):
    if meta['phase'] == 'prefix':
        return {'solution.py': 'broken'}
    return {'solution.py': 'fixed' if meta['action'] == 'restart' else 'overfit'}


def test_missing_draw_is_bounded_not_counted_as_failure():
    estimate = group_estimate([{'action': 'continue', 'draw': 0, 'full_pass': True},
                               {'action': 'restart', 'draw': 0, 'full_pass': False}], 2)
    assert estimate['continue']['lower'] == .5 and estimate['continue']['upper'] == 1
    assert estimate['restart']['lower'] == 0 and estimate['restart']['upper'] == .5
    assert estimate['difference_lower'] == 0 and estimate['difference_upper'] == 1
    assert estimate['repeated_preference'] is None
    with pytest.raises(ValueError):
        group_estimate([{'action': 'continue', 'draw': 0, 'full_pass': None}], 2)


def test_opposite_draws_do_not_establish_repeated_preference():
    candidates = [{'action': a, 'draw': d, 'full_pass': (a == 'continue') == (d == 0)}
                  for a in ['continue', 'restart'] for d in range(2)]
    assert group_estimate(candidates, 2)['repeated_preference'] == 'none'
    with pytest.raises(ValueError):
        group_estimate(candidates + candidates[:1], 2)


def test_report_preserves_public_false_positives_and_pays_loser(tmp_path):
    output = make_bank(tmp_path, repairs)
    report = analyze(output)
    assert report['model_results'] is False and report['currency'] == 'simulated_USD'
    assert report['observed_public_false_positives'] == 4
    assert report['repeated_preferences'] == {'restart': 2}
    policies = {r['policy']: r for r in report['policy_table']}
    assert all(p['common_complete_checkpoints'] == 2 for p in policies.values())
    assert policies['continue_one']['bug_balanced_success'] == 0
    assert policies['restart_one']['bug_balanced_success'] == 1
    assert policies['continue_one']['selected_public_false_positives'] == 2
    assert policies['restart_two_public_select']['bug_balanced_prefix_plus_candidate_cost_usd'] == pytest.approx(.000175)
    assert Decimal(report['known_generation_charges_usd']) == Decimal('.00050')
    assert all('replay_selection_seconds' not in r for r in report['policy_rows'])
    again = analyze(output)
    report.pop('replay_selection_timings')
    again.pop('replay_selection_timings')
    assert report == again
    assert 'not model evidence' in render(report)


def test_analysis_refuses_running_bank_and_requires_explicit_interruption(tmp_path):
    def fail(*_):
        raise TimeoutError('test')
    with pytest.raises(TimeoutError):
        make_bank(tmp_path, fail)
    output = tmp_path / 'bank'
    with pytest.raises(ValueError, match='terminal/interrupted'):
        analyze(output)
    report = analyze(output, allow_interrupted=True)
    assert report['evidence_status'] == 'incomplete_development_calibration'
    assert len(report['unknown_reservations']) == 1
    assert report['observations'] == 0 and report['finished_trajectories'] == 0
    (output / 'interruption.json').unlink()
    with pytest.raises(ValueError):
        analyze(output, allow_interrupted=True)


def test_uncollected_candidates_remain_in_group_bounds_and_outside_common_cohort(tmp_path):
    output = make_bank(tmp_path, repairs, limit='.0003')
    report = analyze(output)
    assert report['evidence_status'] == 'incomplete_development_calibration'
    assert report['eligible_checkpoints'] == 1 and report['complete_checkpoints'] == 0
    assert report['group_table'][0]['difference_lower'] == -1
    assert report['group_table'][0]['difference_upper'] == 1
    assert all(p['bug_balanced_success'] is None for p in report['policy_table'])
    assert all(r['status'] == 'missing' for r in report['policy_rows'])


def test_bug_balance_does_not_weight_longer_prefix_twice(tmp_path):
    first, second = task('synthetic/first'), task('synthetic/second')
    def responder(request, meta):
        if meta['phase'] == 'prefix':
            return {'solution.py': 'fixed' if meta['task_hash'] == second.task_hash and meta['depth'] == 2 else 'broken'}
        return {'solution.py': 'fixed' if meta['task_hash'] == first.task_hash else 'broken'}
    report = analyze(make_bank(tmp_path, responder, tasks=[first, second]))
    assert report['complete_checkpoints'] == 3
    assert all(p['bug_balanced_success'] == .5 for p in report['policy_table'])
    assert report['tasks'] == 2 and len(report['task_table']) == 2


def test_interval_is_reproducible_descriptive_bug_bootstrap():
    assert descriptive_interval([1]) is None
    assert descriptive_interval([0, 0]) == [0, 0]
    assert descriptive_interval([-1, 0, 1]) == descriptive_interval([-1, 0, 1])
