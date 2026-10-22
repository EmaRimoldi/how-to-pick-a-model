"""Feedback privacy, deployment accounting, public stopping, and task budgets."""

from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from vao.decisions.feedback_routing import messages, model_for, trajectory
from vao.decisions.openrouter import BudgetLedger, BudgetStopped


CONFIG = {"seed": 42, "maximum_attempts": 8, "task_budget_usd": .006,
          "input_token_ceiling": 8192, "max_tokens": 1536,
          "models": {"small": {"input_per_million": .1, "output_per_million": .15},
                     "large": {"input_per_million": .25, "output_per_million": 2}}}
TASK = {"task_id": "BigCodeBench/1", "complete_prompt": "def task_func(): pass", "test": "HIDDEN_MARKER",
        "canonical_solution": "REFERENCE_MARKER"}


class Client:
    def __init__(self):
        self.models = []
        self.prompts = []
        self.ledger = SimpleNamespace(stopped=False)

    def complete(self, model, prompt, seed, metadata):
        self.models.append(model)
        self.prompts.append(prompt)
        return {"call": len(self.models), "content": json.dumps({"solution": "def task_func(): return 1"}),
                "cost_usd": .001, "finish_reason": "stop"}


class Verifier:
    def __init__(self, public_pass=False, hidden_pass=False):
        self.public_pass, self.hidden_pass = public_pass, hidden_pass

    def check(self, task, source, mode):
        if mode == "heldout":
            return {"passed": self.hidden_pass, "status": "checked"}
        return {"passed": self.public_pass, "status": "fail", "attempted": 2, "failed": 1,
                "feedback": "PUBLIC_ONLY"}


def test_feedback_projection_excludes_private_fields_and_artifact():
    visible = {"status": "fail", "feedback": "PUBLIC_ONLY", "solution": "CODE_MARKER", "heldout": "HIDDEN_MARKER"}
    payload = json.dumps(messages(TASK, visible))
    assert "PUBLIC_ONLY" in payload
    for secret in ("CODE_MARKER", "REFERENCE_MARKER", "HIDDEN_MARKER"):
        assert secret not in payload


def test_failure_updates_feedback_and_charges_shared_prefix(tmp_path):
    client = Client()
    prefix = {"call": 90, "cost_usd": .001, "visible": {"passed": False, "status": "fail", "feedback": "PREFIX_FEEDBACK"},
              "heldout": None, "verifier_seconds": .2}
    outcome = trajectory(CONFIG, TASK, "small_feedback", client, Verifier(), tmp_path, prefix)
    assert client.models == ["small"] * 4  # Fifth new admission would exceed .006.
    assert "PREFIX_FEEDBACK" in json.dumps(client.prompts[0])
    assert "PUBLIC_ONLY" in json.dumps(client.prompts[1])
    assert outcome["calls"] == [90, 1, 2, 3, 4]
    assert outcome["cost_usd"] == pytest.approx(.005)
    assert outcome["stop_reason"] == "task_budget"


def test_hidden_failure_does_not_trigger_another_attempt(tmp_path):
    client = Client()
    row = trajectory(CONFIG, TASK, "immediate_large_feedback", client, Verifier(True, False), tmp_path)
    assert client.models == ["small"]
    assert row["public_false_positive"] and not row["passed"]
    assert row["stop_reason"] == "public_pass"


def test_large_not_admitted_above_remaining_ceiling(tmp_path):
    client = Client()
    row = trajectory(CONFIG, TASK, "immediate_large_feedback", client, Verifier(), tmp_path)
    assert client.models == ["small"]  # .001 + .00512 > .006.
    assert not row["passed"] and row["stop_reason"] == "task_budget"


def test_delayed_switch_uses_two_small_attempts():
    assert [model_for("delayed_large_feedback", i) for i in range(4)] == ["small", "small", "large", "large"]


def test_new_budget_requires_explicit_maximum_and_keeps_unknown_holds(tmp_path):
    with pytest.raises(ValueError):
        BudgetLedger(tmp_path / "old.jsonl", 5)
    ledger = BudgetLedger(tmp_path / "new.jsonl", 5, maximum_limit_usd=5)
    ledger.reserve(Decimal("4.99"), "uncertain")
    with pytest.raises(BudgetStopped):
        ledger.reserve(Decimal(".02"), "new")
    assert sum(ledger.pending.values()) == Decimal("4.99")


def test_private_assertions_are_never_returned_by_worker(monkeypatch):
    from vao.decisions.bigcode_worker import check
    payload = {"mode": "heldout", "solution": "def task_func(): return False",
               "problem": {"test": "import unittest\nclass TestCases(unittest.TestCase):\n def test_x(self): self.assertTrue(task_func(), 'PRIVATE_ASSERTION')"}}
    # This is synthetic trusted code; real candidates run only through the sandbox.
    import sys
    original_main = sys.modules["__main__"]
    monkeypatch.setitem(sys.modules, "__main__", original_main)
    result = check(payload)
    assert result["passed"] is False
    assert "PRIVATE_ASSERTION" not in json.dumps(result)


def test_full_synthetic_collection_reproduces_and_detects_corruption(tmp_path):
    import hashlib
    from vao.decisions.feedback_routing import collect
    from vao.decisions.openrouter import OpenRouterClient
    from scripts.analyze_feedback_routing import audit, analyze
    config = dict(CONFIG, tasks=2, replicates=3, workers=1, run_ceiling_usd=4.8,
                  bundle=str(tmp_path), task_file="tasks.json", provider="siliconflow/fp8",
                  temperature=.6, request_seed=False)
    config["models"] = {name: dict(m, id="qwen/" + name, reasoning_parameter=False) for name, m in CONFIG["models"].items()}
    tasks = [dict(TASK, task_id="BigCodeBench/" + str(i)) for i in range(2)]
    (tmp_path / "tasks.json").write_text(json.dumps(tasks))
    config["task_sha256"] = hashlib.sha256((tmp_path / "tasks.json").read_bytes()).hexdigest()
    (tmp_path / "config.json").write_text(json.dumps(config))
    (tmp_path / "manifest.json").write_text(json.dumps({"config_sha256": hashlib.sha256((tmp_path / "config.json").read_bytes()).hexdigest()}))
    ledger = BudgetLedger(tmp_path / "budget.jsonl", 4.8, maximum_limit_usd=5)
    client = OpenRouterClient("synthetic_key", config, tmp_path, ledger)
    def request(endpoint, body):
        large = body["model"].endswith("large")
        return {"id": "synthetic", "provider": "SiliconFlow", "model": body["model"],
                "usage": {"cost": .0004 if large else .0001, "prompt_tokens": 100, "completion_tokens": 100},
                "choices": [{"message": {"content": json.dumps({"solution": "def task_func(): return " + str(int(large))})}, "finish_reason": "stop"}]}
    client.request = request
    class SyntheticVerifier:
        def check(self, task, source, mode):
            return {"passed": source.endswith("1"), "status": "pass" if source.endswith("1") else "fail", "feedback": "PUBLIC_ONLY"}
    summary = collect(config, tasks, client, SyntheticVerifier(), tmp_path)
    assert summary["status"] == "complete"
    data = audit(tmp_path)
    report = analyze(data)
    assert report["primary_gate_passed"]
    assert report["contrasts"][0]["estimate"] == 1
    assert data["integrity"]["complete"]
    # A three-replicate bank still has two independent task clusters.
    assert report["task_clusters"] == 2 and report["replicates"] == 3
    outcome_path = tmp_path / "outcomes.jsonl"
    rows = [json.loads(x) for x in outcome_path.read_text().splitlines()]
    rows[0]["cost_usd"] += .001
    outcome_path.write_text("".join(json.dumps(x) + "\n" for x in rows))
    with pytest.raises(AssertionError):
        audit(tmp_path)


@pytest.mark.skipif(__import__("sys").platform != "darwin", reason="macOS sandbox integration")
def test_bigcode_sandbox_public_and_hidden_boundary():
    from vao.decisions.bigcode import BigCodeVerifier
    task = {"complete_prompt": 'def task_func(x):\n    """\n    >>> task_func(2)\n    3\n    """\n', "entry_point": "task_func",
            "test": "import unittest\nclass TestCases(unittest.TestCase):\n def test_x(self): self.assertEqual(task_func(7), 8, 'PRIVATE_ASSERTION')"}
    verifier = BigCodeVerifier(timeout=10)
    assert all(verifier.preflight().values())
    source = "def task_func(x): return x + 1"
    assert verifier.check(task, source, "visible")["passed"]
    assert verifier.check(task, source, "heldout")["passed"]
    wrong = verifier.check(task, "def task_func(x): return 3", "heldout")
    assert not wrong["passed"] and "PRIVATE_ASSERTION" not in json.dumps(wrong)
