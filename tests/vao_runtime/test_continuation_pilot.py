from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from vao.decisions.openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient
from vao.decisions.pilot import ACTIONS, collect, evaluate_response, messages_for, summarize
from vao.decisions.verification import SandboxVerifier
from vao.decisions.verifier_worker import ExampleChecker, public_examples_doc


@pytest.fixture
def config():
    return json.loads(Path("experiments/humaneval-plus/openrouter-continuation-pilot/configs/pilot.json").read_text())


def test_budget_reserves_before_call_and_blocks_overspend(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 0.01)
    call = ledger.reserve(Decimal("0.006"), "small")
    with pytest.raises(BudgetStopped):
        ledger.reserve(Decimal("0.006"), "large")
    ledger.settle(call, 0.002)
    assert ledger.reserve(Decimal("0.006"), "large") == 2
    assert ledger.spent + sum(ledger.pending.values()) == Decimal("0.008")


@pytest.mark.parametrize("cost", [None, -1, "NaN", "Infinity"])
def test_uncertain_billing_retains_reservation_and_stops(tmp_path, cost):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    call = ledger.reserve(Decimal("0.01"), "small")
    with pytest.raises(BudgetStopped):
        ledger.settle(call, cost)
    assert call in ledger.pending
    with pytest.raises(BudgetStopped):
        ledger.reserve(Decimal("0.01"), "small")


def test_unexpected_charge_is_recorded_and_stops(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    call = ledger.reserve(Decimal("0.001"), "small")
    with pytest.raises(BudgetStopped):
        ledger.settle(call, 0.002)
    assert ledger.spent == Decimal("0.002")
    assert ledger.stopped


def test_existing_budget_journal_cannot_be_reused(tmp_path):
    path = tmp_path / "budget.jsonl"
    BudgetLedger(path, 2)
    with pytest.raises(FileExistsError):
        BudgetLedger(path, 2)


def test_transport_is_pinned_and_invalid_output_is_still_billed(tmp_path, config, monkeypatch):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    client = OpenRouterClient("dummy-private-key", config, tmp_path, ledger)
    bodies = []

    def request(endpoint, body):
        assert endpoint == "/chat/completions"
        bodies.append(body)
        assert ledger.pending  # Admission already persisted at the network boundary.
        return {"id": "receipt", "provider": "SiliconFlow", "model": body["model"],
                "usage": {"cost": 0.0001, "prompt_tokens": 20, "completion_tokens": 5},
                "choices": [{"finish_reason": "length", "message": {"content": "not json"}}]}

    monkeypatch.setattr(client, "request", request)
    result = client.complete("small", [{"role": "user", "content": "public task"}], 10, {})
    assert result["cost_usd"] == 0.0001
    assert ledger.spent == Decimal("0.0001")
    assert bodies[0]["provider"]["only"] == ["siliconflow/fp8"]
    assert bodies[0]["provider"]["allow_fallbacks"] is False
    assert bodies[0]["provider"]["require_parameters"] is True
    assert bodies[0]["reasoning"] == {"enabled": False}
    assert "seed" not in bodies[0]
    assert result["seed_sent"] is None
    assert "dummy-private-key" not in (tmp_path / "calls.jsonl").read_text()


def test_network_failure_is_not_retried_or_refunded(tmp_path, config, monkeypatch):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    client = OpenRouterClient("dummy", config, tmp_path, ledger)
    calls = []

    def fail(*args):
        calls.append(1)
        raise BackendStopped("timeout")

    monkeypatch.setattr(client, "request", fail)
    with pytest.raises(BackendStopped):
        client.complete("small", [{"role": "user", "content": "task"}], 10, {})
    assert len(calls) == 1
    assert ledger.pending and ledger.stopped


def test_input_ceiling_blocks_before_reservation(tmp_path, config):
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    client = OpenRouterClient("dummy", config, tmp_path, ledger)
    with pytest.raises(BudgetStopped):
        client.complete("small", [{"role": "user", "content": "x" * 20000}], 1, {})
    assert ledger.calls == 0


def test_handoff_contains_only_observable_checkpoint():
    problem = {"prompt": "public task", "canonical_solution": "PRIVATE_REFERENCE",
               "plus_input": ["PRIVATE_TEST"]}
    checkpoint = {"content": '{"solution":"visible code"}',
                  "feedback": {"status": "fail", "feedback": "public error"},
                  "heldout": {"secret": "PRIVATE_SCORE"}}
    a = messages_for(problem, "continue", checkpoint)
    assert a == messages_for(problem, "switch_context", checkpoint)
    assert all(s not in json.dumps(a) for s in ("PRIVATE_REFERENCE", "PRIVATE_TEST", "PRIVATE_SCORE"))
    assert messages_for(problem, "restart") == messages_for(problem, "switch_fresh")


def test_format_failure_needs_no_code_execution():
    class MustNotExecute:
        def check(self, *args):
            raise AssertionError("invalid JSON must not execute")

    result = evaluate_response({}, {"content": "bad json"}, MustNotExecute())
    assert not result["visible"]["passed"]
    assert not result["heldout"]["passed"]
    truncated = evaluate_response({}, {"content": '{"solution":"def f(): pass"}',
                                      "finish_reason": "length"}, MustNotExecute())
    assert not truncated["heldout"]["passed"]


def test_public_examples_exclude_closing_quotes_and_compare_string_literals():
    doc = public_examples_doc('def f():\n    """\n    >>> f()\n    "hello"\n    """\n')
    assert '"""' not in doc
    checker = ExampleChecker()
    assert checker.check_output('"hello"\n', "'hello'\n", 0)
    assert not checker.check_output('"hello"\n', "'wrong'\n", 0)


def test_incomplete_tasks_are_excluded_from_matched_comparison(config):
    rows = [{"strategy": "cheap_stop", "task_id": "task", "passed": True, "policy_cost_usd": 0.1}]
    result = summarize(rows, config)
    assert result["complete_task_ids"] == []
    assert result["strategies"]["cheap_stop"]["success_rate"] is None


def test_four_arms_use_same_parent_and_charge_shared_prefix_once(tmp_path, config):
    config = {**config, "direct_repeats": 1, "branch_repeats": 2}
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 2)
    seen = []

    class Client:
        def __init__(self):
            self.ledger = ledger

        def complete(self, model, messages, seed, metadata):
            call = ledger.reserve(Decimal("0.01"), model)
            ledger.settle(call, 0.001)
            seen.append((model, messages, metadata))
            return {"call": call, "cost_usd": 0.001,
                    "content": json.dumps({"solution": "def f(): return 0"})}

    class Verifier:
        def check(self, problem, solution, mode):
            return {"passed": False, "status": "fail", "feedback": "public failure"}

    summary = collect(config, [{"task_id": "HumanEval/0", "prompt": "public"}], Client(), Verifier(), tmp_path)
    assert summary["status"] == "complete"
    assert ledger.calls == 10  # initial + direct + four actions, each repeated twice
    for action in ACTIONS:
        assert summary["strategies"][action]["mean_policy_cost_usd"] == 0.002
    assert summary["strategies"]["strong_direct"]["mean_policy_cost_usd"] == 0.001
    assert summary["actual_collection_cost_usd"] == 0.01
    branches = [meta for _, _, meta in seen if meta["action"] in ACTIONS]
    assert all(meta["parent_call"] == 1 for meta in branches)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox integration")
def test_real_sandbox_blocks_home_and_network_and_runs_public_examples():
    pytest.importorskip("evalplus")
    verifier = SandboxVerifier()
    assert all(verifier.preflight().values())
    problem = {"prompt": 'def f(x):\n    """\n    >>> f(2)\n    3\n    """\n', "entry_point": "f"}
    assert verifier.check(problem, "def f(x): return x+1", "visible")["passed"]
    assert not verifier.check(problem, "def f(x): return x", "visible")["passed"]
    denied = verifier.check(problem, 'def f(x):\n    return open("/etc/passwd").read()', "visible")
    assert not denied["passed"]
    predicate = {"prompt": 'def f(x):\n    """\n    >>> f(2) == 3\n    """\n', "entry_point": "f"}
    assert verifier.check(predicate, "def f(x): return x+1", "visible")["passed"]
    assert not verifier.check(predicate, "def f(x): return x", "visible")["passed"]
