from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from vao.decisions.context_value import (ARMS, branch_messages, collect_context,
    forecast_messages, observable_features, parse_forecast, select_tasks)
from vao.decisions.openrouter import BudgetLedger
from vao.decisions.pilot import digest


@pytest.fixture
def study_config():
    return json.loads(Path("experiments/humaneval-plus/context-value/configs/study.json").read_text())


def test_state_projection_and_factorial_inputs_exclude_hidden_scores(study_config):
    problem = {"prompt": "public task", "canonical_solution": "SECRET REFERENCE", "plus_input": "SECRET TEST"}
    checkpoint = {"solution": "def f(): return 1", "feedback": {"status": "fail", "feedback": "public error"},
                  "heldout": "SECRET OUTCOME", "features": {"syntax_valid": True}}
    for arm in ARMS:
        messages = branch_messages(problem, arm, checkpoint)
        serialized = json.dumps(messages)
        assert "SECRET" not in serialized
        payload = json.loads(messages[1]["content"].split("\n", 1)[1])
        assert (payload["previous_solution"] is not None) == (arm in {"artifact", "artifact_feedback"})
        assert (payload["public_example_feedback"] is not None) == (arm in {"feedback", "artifact_feedback"})
    for view in ("task_only", "state"):
        messages = forecast_messages(problem, view, checkpoint, study_config)
        assert "SECRET" not in json.dumps(messages)
        assert ("previous_solution" in json.loads(messages[1]["content"])) == (view == "state")


@pytest.mark.parametrize("content,finish", [('{}', 'stop'), ('{"probabilities":{}}', 'stop'), ('broken', 'length')])
def test_malformed_forecasts_are_counted_with_fallback(study_config, content, finish):
    probabilities, valid = parse_forecast({"content": content, "finish_reason": finish}, study_config)
    assert not valid
    assert len(probabilities) == 8 and set(probabilities.values()) == {0.5}


def test_collect_forecasts_are_saved_before_matched_branches(tmp_path, study_config):
    config = {**study_config, "prefix_repeats": 1, "branch_repeats": 2}
    problem = {"task_id": "HumanEval/0", "prompt": "public prompt"}

    class Client:
        ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)

        def complete(self, model, messages, seed, metadata):
            if metadata["action"] in ARMS:
                saved = [json.loads(line) for line in (tmp_path / "predictions.jsonl").read_text().splitlines()]
                assert len(saved) == 2
                assert all(r["call"] < self.ledger.calls + 1 for r in saved)
            call = self.ledger.reserve(Decimal("0.001"), model)
            self.ledger.settle(call, 0.0001)
            keys = [m + "." + a for m in config["target_models"] for a in ARMS]
            content = {"probabilities": {k: 0.7 for k in keys}} if metadata["action"] == "forecast" else {"solution": "def f(): return 0"}
            return {**metadata, "call": call, "cost_usd": 0.0001, "content": json.dumps(content), "finish_reason": "stop"}

    class Verifier:
        def check(self, problem, solution, mode):
            return {"passed": False, "status": "fail", "feedback": "visible only" if mode == "visible" else "SECRET"}

    result = collect_context(config, [problem], Client(), Verifier(), tmp_path)
    assert result["status"] == "complete"
    assert result["requests"] == 19  # one prefix, two forecasts, sixteen branch draws
    assert result["visible_failed_checkpoints"] == 1
    assert "SECRET" not in (tmp_path / "checkpoints.jsonl").read_text()
    branches = [json.loads(line) for line in (tmp_path / "branches.jsonl").read_text().splitlines()]
    assert len({(r["model_name"], r["arm"], r["draw"]) for r in branches}) == 16
    assert all(r["prefix_and_action_cost_usd"] == 0.0002 for r in branches)


def test_visible_success_never_branches_even_if_hidden_evaluation_fails(tmp_path, study_config):
    config = {**study_config, "prefix_repeats": 1}

    class Client:
        ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)

        def complete(self, model, messages, seed, metadata):
            assert metadata["action"] == "initial"
            call = self.ledger.reserve(Decimal("0.001"), model)
            self.ledger.settle(call, 0.0001)
            return {"call": call, "cost_usd": 0.0001, "content": '{"solution":"def f(): return 0"}'}

    class Verifier:
        def check(self, problem, solution, mode):
            return {"passed": mode == "visible", "status": "pass" if mode == "visible" else "fail"}

    result = collect_context(config, [{"task_id": "HumanEval/0", "prompt": "task"}], Client(), Verifier(), tmp_path)
    assert result["branches"] == 0 and result["forecasts"] == 0


def test_frozen_task_pool_disjoint_from_prior_and_reserve(study_config):
    pytest.importorskip("evalplus")
    problems, reserved, _ = select_tasks(study_config)
    ids = {p["task_id"] for p in problems}
    assert len(ids) == 30 and len(reserved) == 20
    assert not ids & set(reserved)
    assert not (ids | set(reserved)) & set(study_config["excluded_task_ids"])
    assert observable_features("def f(:", {"status": "error", "feedback": "SyntaxError"})["syntax_error"]
