from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from vao.decisions.context_value import ARMS
from vao.decisions.openrouter import BudgetLedger, BudgetStopped, OpenRouterClient
from vao.decisions.recovery import CONDITIONS, forecast_messages, load_experiment, recovery_messages, run
from vao.decisions.recovery_policy import fit_policy, predict
from vao.decisions.verification import SandboxVerifier


@pytest.fixture
def recovery_config():
    return json.loads(Path("experiments/humaneval-plus/context-value/configs/validation.json").read_text())


def test_concurrent_reservations_cannot_overcommit(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 0.02)
    def reserve(_):
        try:
            return ledger.reserve(Decimal("0.006"), "model")
        except BudgetStopped:
            return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        admitted = [i for i in pool.map(reserve, range(40)) if i is not None]
    assert len(admitted) == len(set(admitted)) == 3
    assert sum(ledger.pending.values()) == Decimal("0.018")
    assert len((tmp_path / "budget.jsonl").read_text().splitlines()) == 3


def test_per_model_provider_and_nonreasoning_parameters_are_enforced(tmp_path, recovery_config, monkeypatch):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 1)
    client = OpenRouterClient("dummy", recovery_config, tmp_path, ledger)
    def request(endpoint, body):
        assert body["provider"]["only"] == ["deepinfra/bf16"]
        assert body["provider"]["quantizations"] == ["bf16"]
        assert "reasoning" not in body
        assert body["provider"]["allow_fallbacks"] is False
        return {"provider": "DeepInfra", "model": body["model"], "usage": {"cost": 0.00001, "prompt_tokens": 10, "completion_tokens": 10},
                "choices": [{"finish_reason": "stop", "message": {"content": '{"solution":"pass"}'}}]}
    monkeypatch.setattr(client, "request", request)
    assert client.complete("producer", [{"role": "user", "content": "task"}], 1, {})["cost_usd"] == 0.00001


def test_base_feedback_subprocess_never_receives_plus_inputs(monkeypatch):
    verifier = object.__new__(SandboxVerifier)
    verifier.timeout = 30
    def execute(command, **kwargs):
        payload = json.loads(kwargs["input"])
        assert payload["mode"] == "base_feedback"
        assert "plus_input" not in payload["problem"]
        assert "PRIVATE PLUS" not in kwargs["input"]
        return SimpleNamespace(stdout='{"passed":false,"status":"fail"}', stderr="")
    monkeypatch.setattr("vao.decisions.verification.subprocess.run", execute)
    problem = {"prompt": "public", "entry_point": "f", "canonical_solution": "reference", "base_input": [[1]], "plus_input": "PRIVATE PLUS", "atol": 0}
    assert not verifier.check(problem, "def f(x): return x", "base_feedback")["passed"]


def test_context_and_forecast_projections_exclude_private_tests(recovery_config):
    p = {"prompt": "public task", "plus_input": "PRIVATE PLUS", "canonical_solution": "PRIVATE REFERENCE"}
    cp = {"task_id": "a", "solution": "failed code", "feedback": {"passed": False, "status": "fail", "feedback": "public"}, "heldout": "PRIVATE SCORE"}
    donor = {"task_id": "b", "solution": "other task longer source", "feedback": {"status": "fail", "feedback": "different public feedback"}}
    for arm in CONDITIONS:
        assert "PRIVATE" not in json.dumps(recovery_messages(p, arm, cp, donor))
    relevant = json.loads(recovery_messages(p, "artifact_feedback", cp)[1]["content"].split("\n", 1)[1])
    irrelevant = json.loads(recovery_messages(p, "distractor", cp, donor)[1]["content"].split("\n", 1)[1])
    assert len(relevant["previous_solution"]) == len(irrelevant["previous_solution"])
    assert len(relevant["public_test_feedback"]) == len(irrelevant["public_test_feedback"])
    policy = {"priors": {"small.fresh": 0.5}, "mean_action_cost_usd": {"small.fresh": 0.001}}
    for view in ("task_only", "state"):
        assert "PRIVATE" not in json.dumps(forecast_messages(p, view, cp, policy, recovery_config))


def test_policy_freezes_before_any_evaluation_call_and_predictions_before_branches(tmp_path, recovery_config):
    config = {**recovery_config, "minimum_development_failed_tasks": 2}
    problems = {"a": {"prompt": "a public prompt"}, "b": {"prompt": "b public prompt"}, "c": {"prompt": "c public prompt"}}
    # Numeric IDs are used only to choose a deterministic distractor donor.
    problems = {"HumanEval/" + str(i): p for i, p in enumerate(problems.values())}
    split = {"development_task_ids": ["HumanEval/0", "HumanEval/1"], "evaluation_task_ids": ["HumanEval/2"]}

    class Client:
        ledger = BudgetLedger(tmp_path / "budget.jsonl", 1)
        lock = threading.Lock()
        calls = []
        def complete(self, model, messages, seed, metadata):
            if metadata["split"] == "evaluation":
                assert (tmp_path / "frozen-policy.json").exists()
            if metadata["split"] == "evaluation" and metadata["action"] == "branch":
                assert (tmp_path / "local-predictions.jsonl").exists()
            call = self.ledger.reserve(Decimal("0.0001"), model)
            self.ledger.settle(call, 0.00001)
            content = {"solution": "def f(): return 0"}
            if metadata["action"] == "forecast":
                content = {"probabilities": {m + "." + a: 0.7 for m in config["target_models"] for a in ARMS}}
            row = {**metadata, "call": call, "cost_usd": 0.00001, "content": json.dumps(content), "finish_reason": "stop"}
            with self.lock:
                self.calls.append(row)
            return row

    class Verifier:
        def check(self, problem, source, mode):
            return {"passed": False, "status": "fail", "attempted": 2, "failed": 1, "feedback": "public"}

    client = Client()
    summary = run(config, problems, split, client, Verifier(), tmp_path)
    assert summary["status"] == "complete"
    frozen = json.loads((tmp_path / "frozen-policy.json").read_text())
    assert set(frozen["training_task_ids"]) == set(split["development_task_ids"])
    test_forecasts = [r["call"] for r in client.calls if r["action"] == "forecast"]
    test_branches = [r["call"] for r in client.calls if r["split"] == "evaluation" and r["action"] == "branch"]
    assert max(test_forecasts) < min(test_branches)
    assert all(0 <= p <= 1 for p in predict(frozen, "public", {"solution": "", "feedback": {"status": "format_error"}}, "state").values())


def test_validation_split_is_task_disjoint(recovery_config):
    pytest.importorskip("evalplus")
    _, split = load_experiment(recovery_config)
    assert len(split["development_task_ids"]) == 83
    assert len(split["evaluation_task_ids"]) == 60
    assert len(split["reserved_task_ids"]) == 19
