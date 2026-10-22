from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.analyze_recovery_validation import analyze, audit, paired_interval, reservation, rollout
from vao.decisions.context_value import ARMS
from vao.decisions.openrouter import BudgetLedger, OpenRouterClient
from vao.decisions.pilot import digest
from vao.decisions.recovery import run


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


def test_routing_and_context_ablations_restrict_the_action_menu(replay_data):
    assert rollout("t", "state_model_only", 0.01, replay_data)["selected_action"] == "large.artifact_feedback"
    assert rollout("t", "state_context_small", 0.01, replay_data)["selected_action"] == "small.fresh"


def test_task_bootstrap_includes_zero_and_negative_outcomes():
    r = paired_interval([0, -1, 1, 0, 0])
    assert r["mean"] == 0 and r["task_clusters"] == 5
    assert r["bootstrap_95"][0] < 0 < r["bootstrap_95"][1]


def test_end_to_end_audit_refits_frozen_policy_and_reproduces_forecast_prompts(tmp_path, monkeypatch):
    config = json.loads(Path("experiments/humaneval-plus/context-value/configs/validation.json").read_text())
    config["minimum_development_failed_tasks"] = 2
    split = {"development_task_ids": ["HumanEval/0", "HumanEval/1"], "evaluation_task_ids": ["HumanEval/2"],
             "reserved_task_ids": [], "reference_exclusions": []}
    problems = {task: {"prompt": "public task " + task} for task in split["development_task_ids"] + split["evaluation_task_ids"]}
    manifest = {"config": config, "config_sha256": digest(config), "split": split, "git_sha": "source",
                "prompt_sha256": {task: digest(p["prompt"]) for task, p in problems.items()}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    client = OpenRouterClient("dummy", config, tmp_path, BudgetLedger(tmp_path / "budget.jsonl", 1.97))
    def request(endpoint, body):
        forecast = body["messages"][0]["content"].startswith("A previous Python")
        model = next(k for k, v in config["models"].items() if v["id"] == body["model"])
        content = {"probabilities": {m + "." + a: 0.8 for m in config["target_models"] for a in ARMS}} if forecast else {"solution": "def f(): return " + ("1" if model == "large" else "0")}
        return {"id": "test", "model": body["model"], "provider": "DeepInfra" if model == "producer" else "SiliconFlow",
                "usage": {"cost": 0.0001 if model == "large" else 0.00001, "prompt_tokens": 20, "completion_tokens": 20},
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}
    monkeypatch.setattr(client, "request", request)
    class Verifier:
        def check(self, problem, solution, mode):
            passed = "return 1" in solution
            return {"passed": passed, "status": "pass" if passed else "fail", "attempted": 2, "failed": 0 if passed else 1, "feedback": "public failure"}
    assert run(config, problems, split, client, Verifier(), tmp_path)["status"] == "complete"
    audited = audit(tmp_path)
    report, rows = analyze(audited)
    assert report["audit_passed"] and report["evaluation_tasks"] == 1
    assert report["primary"]["net_utility_difference_usd"]["mean"] == 0
    assert all(r["cost_usd"] <= r["budget_usd"] for r in rows)
    # A score must stay attached to the exact requested draw, even when every
    # receipt and probability is otherwise internally consistent.
    branch_path = tmp_path / "branches.jsonl"
    saved = [json.loads(line) for line in branch_path.read_text().splitlines()]
    evaluation_row = next(row for row in saved if row["split"] == "evaluation")
    evaluation_row["draw"] = 99
    branch_path.write_text("".join(json.dumps(row) + "\n" for row in saved))
    with pytest.raises(ValueError, match="Recovery receipt metadata changed"):
        audit(tmp_path)
