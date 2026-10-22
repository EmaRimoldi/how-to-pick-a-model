from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from vao.decisions.recovery_policy import features, predict
from vao.decisions.transfer import FEEDBACK_FEATURES, choose, collect, freeze, replay
from vao.decisions.openrouter import BudgetLedger


def config():
    return {"training_source": "experiments/humaneval-plus/context-value/results/validation-20261022",
        "target_models": ["small", "large"], "branch_repeats": 3, "maximum_attempts": 2,
        "minimum_development_failed_tasks": 20, "ridge_penalty": 10, "solution_value_usd": .01,
        "task_budgets_usd": [.003, .01, .02], "input_token_ceiling": 24576, "max_tokens": 1536,
        "models": {"small": {"input_per_million": .10, "output_per_million": .15},
                   "large": {"input_per_million": .25, "output_per_million": 2}}}


def test_feedback_ablation_cannot_see_code():
    cp = {"solution": "def f(): return 1", "feedback": {"status": "fail", "attempted": 3, "failed": 1}}
    changed = dict(cp, solution="broken syntax aaaa" * 50)
    assert {k: features("task", cp)[k] for k in FEEDBACK_FEATURES} == {
        k: features("task", changed)[k] for k in FEEDBACK_FEATURES}
    assert features("task", cp)["syntax_valid"] != features("task", changed)["syntax_valid"]


def test_source_training_has_51_tasks_and_only_feedback_view_drops_code():
    policy, data = freeze(config())
    assert len(policy["training_task_ids"]) == len(data["checkpoints"]) == 51
    assert set(policy["fits"]) == {"task", "feedback", "state"}
    cp = data["checkpoints"][0]
    changed = dict(cp, solution="syntax broken" * 100)
    p = data["prompts"][cp["task_id"]]
    assert predict(policy, p, cp, "feedback") == predict(policy, p, changed, "feedback")
    assert set(policy["development_replay_fixed"]) == {"0.003", "0.01", "0.02"}


def test_admission_uses_reservation_and_public_success_not_future_bill_or_hidden_pass():
    cfg = config()
    rows = [{"model_name": "large", "arm": "fresh", "draw": d, "passed": d == 1,
             "visible_passed": True, "incremental_cost_usd": .0001} for d in range(3)]
    # A very cheap eventual receipt cannot make the first large call admissible.
    assert replay(rows, "large.fresh", .0001, cfg, .003)["attempts"] == 0
    outcome = replay(rows, "large.fresh", .0001, cfg, .01)
    assert outcome["attempts"] == 1 and not outcome["passed"]
    assert outcome["termination"] == "public_pass"
    assert outcome["cost_usd"] == pytest.approx(.0002)


def test_model_only_cannot_select_a_different_context():
    cfg = config()
    p = {m + "." + a: .9 if a == "fresh" else .5 for m in cfg["target_models"]
         for a in ("fresh", "artifact", "feedback", "artifact_feedback")}
    policy = {"mean_action_cost_usd": {k: .0001 for k in p}}
    assert choose(policy, p, cfg, .02, .0001).endswith(".fresh")
    assert choose(policy, p, cfg, .02, .0001, "model_only").endswith(".artifact_feedback")


@pytest.mark.parametrize("budget", [.1, 1.0])
def test_budget_block_gate_preserves_all_selected_states_and_prospective_predictions(tmp_path, monkeypatch, budget):
    cfg = dict(config(), maximum_checkpoints=96, seed=20261025, workers=4, verifier_workers=2, prior_committed_usd=.5149634)
    policy, source = freeze(cfg)
    class Client:
        ledger = BudgetLedger(tmp_path / "budget.jsonl", budget)
        def complete(self, model, messages, seed, metadata):
            if metadata["action"] != "initial":
                assert budget == 1.0
                assert len((tmp_path / "local-predictions.jsonl").read_text().splitlines()) == 3
            call = self.ledger.reserve(Decimal(".001"), model)
            self.ledger.settle(call, .00001)
            return {**metadata,"call":call,"cost_usd":.00001}
    monkeypatch.setattr("vao.decisions.transfer.evaluate", lambda *_: {
        "solution":"def f(): return 0","solution_sha256":"hash", "verifier_seconds":0,
        "visible":{"passed":False,"status":"fail","attempted":3,"failed":1},"heldout":{"passed":False}})
    tasks = ["Mbpp/2", "Mbpp/3", "Mbpp/4"]
    outcome = collect(cfg,tasks,{t:{"prompt":"public"} for t in tasks},policy,source,Client(),None,tmp_path)
    assert outcome["status"] == ("budget_block_gate" if budget == .1 else "complete")
    assert outcome["branch_responses"] == (0 if budget == .1 else 90)
    selected = json.loads((tmp_path / "selection.json").read_text())["selected_checkpoint_ids"]
    predictions = [json.loads(s) for s in (tmp_path / "local-predictions.jsonl").read_text().splitlines()]
    assert len(selected) == len(predictions) == 3
    assert all(r["last_admitted_call"] == 3 for r in predictions)


@pytest.mark.skipif(sys.platform != "darwin", reason="Live verifier requires macOS sandbox-exec")
def test_mbpp_special_oracles_and_complex_transport():
    pytest.importorskip("evalplus")
    from evalplus.data import get_mbpp_plus
    from vao.decisions.verification import SandboxVerifier
    problems, v = get_mbpp_plus(), SandboxVerifier()
    # Set-equality, complex input and output-not-None rules must retain official semantics.
    from evalplus.eval._special_oracle import MBPP_OUTPUT_NOT_NONE_TASKS
    ids = ["Mbpp/2", "Mbpp/124", "Mbpp/252"]
    ids += [t for t,p in problems.items() if p["entry_point"] in MBPP_OUTPUT_NOT_NONE_TASKS][:1]
    for t in ids:
        p = dict(problems[t], dataset="mbpp")
        solution = p["prompt"] + p["canonical_solution"]
        assert v.check(p, solution, "base_feedback")["passed"], t
        assert v.check(p, solution, "heldout")["passed"], t
