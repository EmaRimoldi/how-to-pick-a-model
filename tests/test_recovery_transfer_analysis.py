from __future__ import annotations

import importlib.util
import itertools
import json
import random
from pathlib import Path

import numpy as np
import pytest


def analyzer():
    spec = importlib.util.spec_from_file_location("transfer_analysis", Path("scripts/analyze_recovery_transfer.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_interval_clusters_tasks_and_is_reproducible():
    a = analyzer()
    values = [0, .5, -.5, 1]
    assert a.interval(values) == a.interval(values)
    assert a.interval(values)["estimate"] == pytest.approx(.25)
    ordinary, corrected = a.interval(values), a.interval(values, .05/8)
    assert corrected["low"] <= ordinary["low"] <= ordinary["high"] <= corrected["high"]


def test_variance_diagnostic_does_not_clip_negative_noise_estimates():
    a = analyzer()
    # Observed per-task sample means vary, despite a negative noise-corrected variance.
    draws = np.array([[1,0,-1], [0,-1,1], [1,1,-1]], dtype=float)
    assert a.variance_stat(draws) < 0
    constant = np.ones((10,3))
    assert a.variance_stat(constant) == pytest.approx(0)


def test_frozen_comparison_tolerates_roundoff_but_rejects_material_changes():
    a = analyzer()
    assert a.same({"coefficient": [.1]}, {"coefficient": [.1+1e-14]})
    assert not a.same({"coefficient": [.1]}, {"coefficient": [.11]})
    assert not a.same({"coefficient": [.1]}, {"different": [.1]})


@pytest.mark.parametrize("interrupt",[False,True])
def test_offline_audit_roundtrip_from_mocked_collection_and_rejects_model_drift(tmp_path,interrupt):
    """Exercise journals, prospective order and matched-cell statistics without APIs/program execution."""
    from vao.decisions.openrouter import BackendStopped,BudgetLedger, OpenRouterClient
    from vao.decisions.pilot import digest
    from vao.decisions.transfer import collect, freeze,import_prefixes,file_hash
    first=tmp_path/"first";first.mkdir()
    cfg=json.loads(Path("experiments/mbpp-plus/context-value-transfer/configs/replication.json").read_text())
    cfg["maximum_checkpoints"]=2
    reference=[json.loads(s) for s in Path(cfg["reference_audit"]).read_text().splitlines()]
    tasks=sorted({r["task_id"] for r in reference}-set(cfg["reference_exclusions"]),key=lambda t:int(t.split("/")[1]))
    random.Random(cfg["seed"]).shuffle(tasks)
    problems={t:{"prompt":"public synthetic task "+t} for t in tasks}
    policy,source=freeze(cfg)
    # This is a newly frozen synthetic fixture on the current BLAS platform,
    # rather than the campaign's already committed macOS weight bytes.
    cfg["source_policy_digest"]=digest(policy)
    manifest={"config":cfg,"task_order":tasks,"policy_sha256":digest(policy),
        "prompt_sha256":{t:digest(p["prompt"]) for t,p in problems.items()},
        "source_sha256":{str(p):file_hash(p) for p in Path("src/vao/decisions").glob("*.py")}}
    (first/"manifest.json").write_text(json.dumps(manifest))
    (first/"frozen-policy.json").write_text(json.dumps(policy,sort_keys=True,indent=2)+"\n")
    client=OpenRouterClient("dummy",cfg,first,BudgetLedger(first/"budget.jsonl",1))
    counter=itertools.count()
    requested=[]
    should_stop=interrupt
    def request(endpoint,body):
        model=next(k for k,v in cfg["models"].items() if v["id"]==body["model"])
        if model=="producer":
            task=body["messages"][0]["content"].split("public synthetic task ",1)[1]
            requested.append(task)
            if should_stop and task==tasks[2]:raise BackendStopped("OpenRouter URLError; no automatic retry")
        passing=model=="large"
        if model=="small":
            payload=json.loads(body["messages"][1]["content"].split("\n",1)[1])
            passing=payload["previous_solution"] is None
        return {"id":"mock-"+str(next(counter)),"model":body["model"],"provider":"Mistral" if model=="producer" else "SiliconFlow",
            "usage":{"cost":.000001,"prompt_tokens":10,"completion_tokens":10},
            "choices":[{"finish_reason":"stop","message":{"content":json.dumps({"solution":"def f(): return "+("1" if passing else "0")})}}]}
    client.request=request
    class Verifier:
        def check(self,problem,solution,mode):
            passed="return 1" in solution
            status="pass" if passed else "fail"
            return {"passed":passed,"status":{"base":status,"plus":status} if mode=="heldout" else status,
                "attempted":3,"failed":0 if passed else 1,"feedback":"public"}
    result=collect(cfg,tasks,problems,policy,source,client,Verifier(),first)
    final=first
    if interrupt:
        assert result["status"].startswith("BackendStopped")
        assert client.ledger.pending and len(requested)==3
        final=tmp_path/"continued";final.mkdir()
        ledger=BudgetLedger(final/"budget.jsonl",1)
        prefixes=import_prefixes(first,final,ledger,cfg,policy,tasks)
        client=OpenRouterClient("dummy",cfg,final,ledger);client.request=request
        should_stop=False
        result=collect(cfg,tasks,problems,policy,source,client,Verifier(),final,prefixes)
        assert result["status"]=="complete_with_censored_prefix"
        assert all(requested.count(t)==1 for t in tasks)
        assert list(ledger.pending)==[3]
    else:
        assert result["status"]=="complete"
    assert result["branch_responses"]==60
    a=analyzer();data=a.audit(final);report,_=a.analyze(data)
    assert report["status"]=="complete_confirmatory_bank"
    assert report["effects"]["small"]["artifact_feedback-feedback"]["ordinary_95"]["estimate"]==-1
    assert report["model_context_interactions"]["artifact_feedback-feedback"]["ordinary_95"]["estimate"]==-1
    # A semantic predictor can improve Brier while selecting the same action
    # and delivering exactly zero policy benefit after its forecast fee.
    from vao.decisions.context_value import parse_forecast
    from vao.decisions.transfer_forecast import messages
    forecasts=tmp_path/"forecasts";forecasts.mkdir()
    frozen_path=tmp_path/"semantic-freeze.json"
    source_hash=file_hash(Path("src/vao/decisions/transfer_forecast.py"))
    frozen_path.write_text(json.dumps({"target_responses_at_freeze_check":0,"source_primary_manifest_sha256":file_hash(final/"manifest.json"),"source_file_sha256":source_hash}))
    forecast_manifest={"config":cfg,"source_manifest_sha256":file_hash(final/"manifest.json"),"semantic_freeze_sha256":file_hash(frozen_path),
        "source_file_sha256":source_hash,"source_policy_sha256":digest(policy),"prior_upper_usd":data["collection"]["campaign_upper_usd"],"maximum_new_budget_usd":.08}
    (forecasts/"manifest.json").write_text(json.dumps(forecast_manifest))
    forecaster=OpenRouterClient("dummy",cfg,forecasts,BudgetLedger(forecasts/"budget.jsonl",.08))
    def forecast_request(endpoint,body):
        payload=json.loads(body["messages"][1]["content"])
        state="previous_solution" in payload
        probabilities={k:(.1 if k in {"small.artifact","small.artifact_feedback"} else .9) if state else .5 for k in policy["priors"]}
        return {"id":"forecast-"+str(next(counter)),"model":body["model"],"provider":"SiliconFlow", "usage":{"cost":.000001,"prompt_tokens":10,"completion_tokens":10},
            "choices":[{"finish_reason":"stop","message":{"content":json.dumps({"probabilities":probabilities})}}]}
    forecaster.request=forecast_request
    from vao.decisions.openrouter import append_json
    for id_ in data["complete"]:
        cp=data["checkpoints"][id_]
        for view in ("task_only","feedback_only","state"):
            call=forecaster.complete("small",messages(data["prompts"][cp["task_id"]],cp,policy,cfg,view),1,
                {"action":"forecast","model_name":"small","task_id":cp["task_id"],"checkpoint_id":id_,"view":view})
            p,valid=parse_forecast(call,cfg)
            append_json(forecasts/"predictions.jsonl",{"call":call["call"],"task_id":cp["task_id"],"checkpoint_id":id_,"view":view,"probabilities":p,"valid":valid,"cost_usd":call["cost_usd"]})
    semantic,_=a.analyze_semantic(data,forecasts,freeze_path=frozen_path)
    assert semantic["complete_states"]==2
    assert semantic["prediction_metrics"]["state"]["brier"]<semantic["prediction_metrics"]["feedback_only"]["brier"]
    assert semantic["state_feedback_utility"]["estimate"]==pytest.approx(0)
    assert semantic["collection"]["known_cost_usd"]==pytest.approx(.000006)
    # Publishing must reject duplicated provider responses and unexplained or
    # repeated uncertain admissions, even when the small dollar amount fits.
    call_path=forecasts/"calls.jsonl";original_calls=call_path.read_bytes()
    call_path.write_bytes(original_calls+original_calls.splitlines(keepends=True)[0])
    with pytest.raises(ValueError,match="Duplicate semantic response identity"):
        a.analyze_semantic(data,forecasts,freeze_path=frozen_path)
    call_path.write_bytes(original_calls)
    budget_path=forecasts/"budget.jsonl";original_budget=budget_path.read_bytes()
    append_json(budget_path,{"event":"reserve","call":7,"model":"small","reserved_usd":.002688})
    with pytest.raises(ValueError,match="Unexplained unresolved semantic reservation"):
        a.analyze_semantic(data,forecasts,freeze_path=frozen_path)
    cp=data["checkpoints"][data["complete"][0]]
    append_json(forecasts/"transport.jsonl",{"call":7,"action":"forecast","model_name":"small",
        "checkpoint_id":cp["checkpoint_id"],"task_id":cp["task_id"],"view":"state"})
    with pytest.raises(ValueError,match="Repeated semantic state/view admission"):
        a.analyze_semantic(data,forecasts,freeze_path=frozen_path)
    budget_path.write_bytes(original_budget);(forecasts/"transport.jsonl").unlink()
    a.analyze_semantic(data,forecasts,freeze_path=frozen_path)
    rows=[json.loads(s) for s in (final/"calls.jsonl").read_text().splitlines()]
    rows[0]["returned_model"]="unplanned/model"
    (final/"calls.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
    with pytest.raises(ValueError):a.audit(final)
