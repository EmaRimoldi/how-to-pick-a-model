from __future__ import annotations

import json

import pytest

from vao.decisions.pilot import SYSTEM
from vao.decisions.transfer_forecast import messages, public_inputs


def test_semantic_feedback_projection_excludes_code_and_all_views_exclude_hidden_labels():
    cp={"solution":"UNIQUE CODE CONTENT", "feedback":{"status":"fail","feedback":"public evidence"},
        "heldout":"PRIVATE PLUS LABEL", "plus_input":"PRIVATE PLUS INPUT"}
    policy={"priors":{"small.fresh":.5},"mean_action_cost_usd":{"small.fresh":.0001}}
    cfg={"models":{"producer":{"id":"producer"},"small":{"id":"small"},"large":{"id":"large"}},"target_models":["small","large"]}
    for view in ("task_only","feedback_only","state"):
        msg=messages("public task",cp,policy,cfg,view)
        text=json.dumps(msg)
        assert "PRIVATE PLUS" not in text
        assert ("UNIQUE CODE CONTENT" in text) == (view=="state")
        assert ("public evidence" in text) == (view!="task_only")
    assert messages("task",cp,policy,cfg,"feedback_only")[0] == messages("task",cp,policy,cfg,"state")[0]


def test_forecast_budget_carries_unknown_reservations_and_refuses_concurrent_collection(tmp_path):
    files={"manifest.json":{"config":{"prior_committed_usd":.5149634}},"frozen-policy.json":{},
        "selection.json":{"selected_checkpoint_ids":["1"]}}
    for n,r in files.items():(tmp_path/n).write_text(json.dumps(r))
    (tmp_path/"checkpoints.jsonl").write_text(json.dumps({"checkpoint_id":"1","task_id":"Mbpp/2","solution":"code","feedback":{}})+"\n")
    (tmp_path/"calls.jsonl").write_text(json.dumps({"action":"initial","task_id":"Mbpp/2","messages":[{"content":SYSTEM+"\n\npublic prompt"}]})+"\n"+json.dumps({"action":"branch","content":"PRIVATE RECOVERY OUTCOME"})+"\n")
    (tmp_path/"budget.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"event":"reserve","call":1,"reserved_usd":.2},{"event":"settle","call":1,"cost_usd":.1},
        {"event":"reserve","call":2,"reserved_usd":.2}])+"\n")
    with pytest.raises(ValueError,match="still active"):public_inputs(tmp_path)
    (tmp_path/"summary.json").write_text("{}")
    public=public_inputs(tmp_path)
    assert float(public["prior_upper"]) == pytest.approx(.8149634)
    assert "PRIVATE RECOVERY OUTCOME" not in json.dumps(public,default=str)
