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
    rows=[json.loads(s) for s in (final/"calls.jsonl").read_text().splitlines()]
    rows[0]["returned_model"]="unplanned/model"
    (final/"calls.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows))
    with pytest.raises(ValueError):a.audit(final)
