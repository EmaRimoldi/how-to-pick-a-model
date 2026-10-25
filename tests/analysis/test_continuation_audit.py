from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.analysis.analyze_continuation_pilot import audit
from vao.decisions.pilot import STRATEGIES, summarize


@pytest.fixture
def saved_run(tmp_path: Path) -> Path:
    config = {"branch_repeats": 1, "direct_repeats": 1}
    rows = [{"strategy": s, "task_id": "HumanEval/0", "call": 2 if s == "strong_direct" else 1,
             "passed": s == "strong_direct", "policy_cost_usd": 0.0003 if s == "strong_direct" else 0.0001}
            for s in STRATEGIES]
    summary = summarize(rows, config)
    summary.update(actual_collection_cost_usd=0.0004, budget_usd=2)
    (tmp_path / "manifest.json").write_text(json.dumps({"config": config}))
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    calls = [{"call": i, "task_id": "HumanEval/0", "action": action, "provider": "SiliconFlow",
              "seed_sent": None, "elapsed_seconds": 1, "usage": {"cost": cost}}
             for i, action, cost in ((1, "initial", 0.0001), (2, "strong_direct", 0.0003))]
    budget = [{"event": event, "call": i, **values}
              for i, cost in ((1, 0.0001), (2, 0.0003))
              for event, values in (("reserve", {"reserved_usd": 0.01}), ("settle", {"cost_usd": cost}))]
    evaluations = [{"call": i, "visible": {"passed": True}, "heldout": {"passed": i == 2},
                    "verifier_seconds": 0.1} for i in (1, 2)]
    for filename, data in (("calls", calls), ("budget", budget), ("outcomes", rows), ("evaluations", evaluations)):
        (tmp_path / (filename + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in data))
    return tmp_path


def test_audit_distinguishes_reused_outcomes_from_paid_branches(saved_run):
    report = audit(saved_run)
    assert report["model_calls"] == 2
    assert report["actual_continuation_calls"] == 0
    assert report["generation_cost_usd"] == 0.0004
    assert report["false_positive_initial_task_ids"] == ["HumanEval/0"]


def test_audit_rejects_receipt_tampering(saved_run):
    path = saved_run / "calls.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    rows[0]["usage"]["cost"] = 0.0002
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(AssertionError, match="Receipt/settlement"):
        audit(saved_run)


def test_audit_rejects_duplicate_settlements(saved_run):
    path = saved_run / "budget.jsonl"
    with path.open("a") as handle:
        handle.write(json.dumps({"event": "settle", "call": 1, "cost_usd": 0.0001}) + "\n")
    with pytest.raises(AssertionError, match="Duplicate settlement"):
        audit(saved_run)
