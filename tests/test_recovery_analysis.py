from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.analyze_recovery_validation import paired_interval, reservation, rollout


@pytest.fixture
def replay_data():
    config = {"producer": "producer", "input_token_ceiling": 100, "max_tokens": 100,
        "branch_repeats": 2, "maximum_attempts": 2, "solution_value_usd": 0.01,
        "models": {"producer": {"input_per_million": 1, "output_per_million": 1},
                   "small": {"input_per_million": 1, "output_per_million": 1},
                   "large": {"input_per_million": 2, "output_per_million": 2}}}
    probabilities = {"small.fresh": 0.7, "large.artifact_feedback": 0.9}
    rows = [{"task_id": "t", "split": "evaluation", "model_name": model, "arm": arm, "draw": draw,
        "passed": draw == 1, "visible_passed": draw == 1, "incremental_cost_usd": cost}
        for model, arm, cost in (("small", "fresh", 0.00005), ("large", "artifact_feedback", 0.0001)) for draw in range(2)]
    return {"config": config, "policy": {"priors": probabilities,
        "best_fixed_action": "large.artifact_feedback", "mean_action_cost_usd": {"small.fresh": 0.00005, "large.artifact_feedback": 0.0001}},
        "initial": [{"task_id": "t", "cost_usd": 0.00003, "passed": False, "visible_passed": False}],
        "checkpoints": [{"task_id": "t", "checkpoint_id": "1"}],
        "local": [{"task_id": "t", "probabilities": {v: probabilities for v in ("global", "task", "state")}}],
        "forecasts": [{"task_id": "t", "view": "state", "cost_usd": 0.00004, "probabilities": probabilities}], "branches": rows}


def test_budget_admission_does_not_peek_at_future_bill(replay_data):
    # Large worst-case reservation is 0.0004. A future cheap bill does not make
    # the first draw admissible when the remaining budget is only 0.00027.
    r = rollout("t", "best_fixed", 0.0003, replay_data)
    assert not r["passed"] and r["attempts_after_prefix"] == 0
    assert r["cost_usd"] == 0.00003
    assert r["termination"] == "budget"


def test_failed_attempts_prefix_and_forecast_are_all_charged(replay_data):
    r = rollout("t", "api_state", 0.01, replay_data)
    assert r["passed"] and r["attempts_after_prefix"] == 2
    assert r["cost_usd"] == pytest.approx(0.00027)
    assert r["net_utility_usd"] == pytest.approx(0.01 - 0.00027)


def test_public_false_positive_stops_without_using_hidden_score(replay_data):
    replay_data["branches"][2].update(visible_passed=True, passed=False)
    r = rollout("t", "best_fixed", 0.01, replay_data)
    assert not r["passed"] and r["attempts_after_prefix"] == 1
    assert r["termination"] == "public_pass"
    assert r["cost_usd"] == pytest.approx(0.00013)


def test_direct_control_does_not_pay_the_producer(replay_data):
    r = rollout("t", "direct_small", 0.01, replay_data)
    assert r["passed"] and r["cost_usd"] == 0.0001


def test_state_policy_uses_only_budget_admissible_actions(replay_data):
    r = rollout("t", "state", 0.0003, replay_data)
    assert r["selected_action"] == "small.fresh"
    # After paying the first bill, the second remains admissible.
    assert r["passed"] and r["cost_usd"] <= 0.0003


def test_task_bootstrap_includes_zero_and_negative_outcomes():
    r = paired_interval([0, -1, 1, 0, 0])
    assert r["mean"] == 0 and r["task_clusters"] == 5
    assert r["bootstrap_95"][0] < 0 < r["bootstrap_95"][1]
