from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analyze_context_value import audit, estimate_by_task, paired_analysis
from vao.decisions.context_value import ARMS, collect_context
from vao.decisions.openrouter import BudgetLedger, OpenRouterClient
from vao.decisions.pilot import digest


def test_task_macro_weighting_does_not_treat_checkpoints_as_independent_tasks():
    result = estimate_by_task({"task-a": [0, 0, 0], "task-b": [1]})
    assert result["mean"] == 0.5
    assert result["task_clusters"] == 2
    assert result["task_cluster_bootstrap_95"] is None


def test_paired_analysis_excludes_partial_checkpoints_and_rejects_duplicates():
    config = {"target_models": ["small"], "branch_repeats": 1}
    checkpoints = [{"checkpoint_id": "1", "task_id": "a", "features": {}},
                   {"checkpoint_id": "2", "task_id": "b", "features": {}}]
    rows = [{"checkpoint_id": cp, "task_id": task, "model_name": "small", "arm": arm,
             "draw": 0, "passed": arm != "fresh", "incremental_cost_usd": 0.1}
            for cp, task in (("1", "a"), ("2", "b")) for arm in (ARMS if cp == "1" else ARMS[:1])]
    predictions = [{"checkpoint_id": cp, "view": view, "valid": True,
                    "probabilities": {"small." + a: 0.7 for a in ARMS}}
                   for cp in ("1", "2") for view in ("task_only", "state")]
    result = paired_analysis(checkpoints, rows, predictions, config)
    assert result["complete_checkpoint_ids"] == ["1"]
    assert result["incomplete_checkpoint_ids"] == ["2"]
    assert result["contrasts"]["small.both_minus_fresh"]["mean"] == 1
    with pytest.raises(ValueError, match="Duplicate matched branch"):
        paired_analysis(checkpoints, rows + rows[:1], predictions, config)


@pytest.fixture
def context_run(tmp_path, monkeypatch):
    config = json.loads(Path("experiments/humaneval-plus/context-value/configs/study.json").read_text())
    config.update(prefix_repeats=1, branch_repeats=1)
    problem = {"task_id": "HumanEval/0", "prompt": "public task"}
    manifest = {"config": config, "config_sha256": digest(config), "task_ids": [problem["task_id"]], "reserved_task_ids": []}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    client = OpenRouterClient("dummy", config, tmp_path, BudgetLedger(tmp_path / "budget.jsonl", 2))

    def request(endpoint, body):
        is_forecast = body["messages"][0]["content"].startswith("Predict the probability")
        keys = [m + "." + a for m in config["target_models"] for a in ARMS]
        content = {"probabilities": {key: 0.7 for key in keys}} if is_forecast else {"solution": "def f(): return 0"}
        return {"id": "receipt", "provider": "SiliconFlow", "model": body["model"],
            "usage": {"cost": 0.0001, "prompt_tokens": 100, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]}

    monkeypatch.setattr(client, "request", request)

    class Verifier:
        def check(self, problem, solution, mode):
            return {"passed": False, "status": "fail", "feedback": "public error"}

    collect_context(config, [problem], client, Verifier(), tmp_path)
    return tmp_path


def mutate(path, name, transform):
    file = path / (name + ".jsonl")
    rows = [json.loads(line) for line in file.read_text().splitlines()]
    transform(rows)
    file.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_receipts_observable_prompts_and_prospective_order_are_audited(context_run):
    result = audit(context_run)
    assert result["billing_and_prospective_order_verified"]
    assert result["model_calls"] == 11
    assert result["analysis"]["complete_checkpoint_ids"] == ["1"]


def test_audit_rejects_altered_forecast_probability(context_run):
    mutate(context_run, "predictions", lambda rows: rows[0]["probabilities"].update({"small.fresh": 0.99}))
    with pytest.raises(ValueError, match="Forecast parse changed"):
        audit(context_run)


def test_audit_rejects_hidden_result_changes(context_run):
    mutate(context_run, "branches", lambda rows: rows[0].update(passed=True))
    with pytest.raises(ValueError, match="Branch score mismatch"):
        audit(context_run)


def test_audit_rejects_unbilled_branch_price(context_run):
    mutate(context_run, "branches", lambda rows: rows[0].update(incremental_cost_usd=0))
    with pytest.raises(ValueError, match="Branch cost mismatch"):
        audit(context_run)
