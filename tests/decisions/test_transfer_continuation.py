import itertools
import json
from concurrent.futures import wait
from pathlib import Path

import pytest

from vao.decisions.openrouter import BackendStopped, BudgetStopped, BudgetLedger, OpenRouterClient, append_json
from vao.decisions.pilot import digest
from vao.decisions.transfer import file_hash, records, reservation
from vao.decisions.transfer_continuation import cell, collect_unadmitted, import_bank, remaining_jobs


class Verifier:
    def check(self, problem, source, mode):
        return {"passed": True, "status": "pass"}


def fixture(root):
    root.mkdir()
    cfg=json.loads(Path("experiments/mbpp-plus/context-value-transfer/configs/replication.json").read_text())
    cp={"checkpoint_id":"1","parent_call":1,"task_id":"Mbpp/1","solution":"def f(): return 0",
        "feedback":{"passed":False,"status":"fail","failed":1,"attempted":3,"feedback":"public"}}
    cps={"1":cp};selected=["1"]
    counter=itertools.count();requested=[]
    client=OpenRouterClient("dummy",cfg,root,BudgetLedger(root/"budget.jsonl",.5))
    def request(endpoint,body):
        requested.append(body)
        return {"id":"mock-"+str(next(counter)),"model":body["model"],"provider":"SiliconFlow",
                "usage":{"cost":.000001,"prompt_tokens":10,"completion_tokens":10},
                "choices":[{"finish_reason":"stop","message":{"content":json.dumps({"solution":"def f(): return 1"})}}]}
    client.request=request
    expected=remaining_jobs(cfg,selected,cps,[],[])
    for job in expected[:3]:
        call=client.complete(job["model_name"],[{"role":"user","content":"synthetic"}],1,job)
        append_json(root/"branches.jsonl",dict(job,call=call["call"],passed=True,visible_passed=True,incremental_cost_usd=.000001))
        append_json(root/"evaluations.jsonl",{"call":call["call"],"task_id":job["task_id"]})
    unknown=next(r for r in expected if r["model_name"]=="large" and r["arm"]=="artifact" and r["draw"]==2)
    n=client.ledger.reserve(reservation(cfg,"large"),cfg["models"]["large"]["id"])
    append_json(root/"transport.jsonl",dict(unknown,call=n))
    jobs=remaining_jobs(cfg,selected,cps,records(root,"branches"),records(root,"transport"))
    return cfg,selected,cps,jobs,client,requested


def test_only_unadmitted_cells_run_and_censor_survives(tmp_path):
    root=tmp_path/"fixture"
    cfg,selected,cps,jobs,client,requested=fixture(root)
    known={cell(r) for r in records(root,"branches")};uncertain={cell(r) for r in records(root,"transport")}
    assert len(jobs)==26 and not ({cell(r) for r in jobs}&(known|uncertain))
    result=collect_unadmitted(cfg,selected,cps,jobs,{"Mbpp/1":{"prompt":"synthetic"}},[dict(cps["1"],task_id="HumanEval/0",checkpoint_id="donor")],client,Verifier(),root)
    assert result["status"]=="all_unadmitted_jobs_collected_with_censored_cells"
    assert len(requested)==29 and result["branch_responses"]==29
    assert result["complete_states"]==0  #29 observed cells do not become a complete30-cell bank.
    assert list(client.ledger.pending)==[4]
    assert len({cell(r) for r in records(root,"branches")})==29
    assert len(records(root,"calls"))==len(records(root,"evaluations"))==29


@pytest.mark.parametrize("budget_first",[False,True])
def test_new_uncertainty_stops_and_import_preserves_every_admission(tmp_path,monkeypatch,budget_first):
    if budget_first:
        # Reproduce the Linux failure deterministically, rather than relying
        # on a particular thread schedule to exercise the shutdown contract.
        def completed_budget_first(futures):
            futures=list(futures);wait(futures)
            return sorted(futures,key=lambda f:0 if isinstance(f.exception(),BudgetStopped) else 1)
        monkeypatch.setattr("vao.decisions.transfer_continuation.as_completed",completed_budget_first)
    root=tmp_path/"fixture"
    cfg,selected,cps,jobs,client,requested=fixture(root)
    failed_requests=[]
    def fail(endpoint,body):
        failed_requests.append(body)
        raise BackendStopped("OpenRouter URLError; no automatic retry")
    client.request=fail
    result=collect_unadmitted(cfg,selected,cps,jobs,{"Mbpp/1":{"prompt":"synthetic"}},[dict(cps["1"],task_id="HumanEval/0",checkpoint_id="donor")],client,Verifier(),root)
    # Siblings may finish budget errors first, but summary must retain the
    # backend cause required by the explicit transport-continuation contract.
    assert result["status"].startswith("BackendStopped")
    assert failed_requests  #A real mocked backend error, not an exhausted fixture cap.
    assert client.ledger.stopped and 4 in client.ledger.pending and len(client.ledger.pending)>=2
    new_unknowns={r["call"] for r in records(root,"transport") if r["call"]!=4}
    assert len(new_unknowns)==len(failed_requests)
    assert set(client.ledger.pending)=={4}|new_unknowns
    assert len(requested)==3
    (root/"manifest.json").write_text(json.dumps({"config":cfg,"policy_sha256":digest({}),"source_sha256":{}}))
    (root/"frozen-policy.json").write_text("{}")
    (root/"selection.json").write_text(json.dumps({"selected_checkpoint_ids":selected}))
    append_json(root/"checkpoints.jsonl",cps["1"])
    pending=remaining_jobs(cfg,selected,cps,records(root,"branches"),records(root,"transport"))
    frozen={"approved_source_sha256":{p.name:file_hash(p) for p in root.iterdir()},
            "original_manifest_sha256":file_hash(root/"manifest.json"),"authorization":"mock fixture only",
            "authorized_unadmitted_cells":[list(cell(r)) for r in pending]}
    out=tmp_path/"continued";out.mkdir()
    ledger=BudgetLedger(out/"budget.jsonl",.5)
    _,_,_,remaining=import_bank(root,out,ledger,frozen)
    assert remaining==pending
    assert ledger.spent==client.ledger.spent and ledger.pending==client.ledger.pending
    assert ledger.calls==client.ledger.calls and file_hash(out/"budget.jsonl")==file_hash(root/"budget.jsonl")
    assert not (out/"summary.json").exists()  #A new active segment must not look finished to forecasters.
    # A later transport stop may continue only a subset of the original plan.
    next_job=remaining[0]
    n=ledger.reserve(reservation(cfg,next_job["model_name"]),cfg["models"][next_job["model_name"]]["id"])
    assert n==client.ledger.calls+1
    append_json(out/"transport.jsonl",dict(next_job,call=n))
    (out/"summary.json").write_text(json.dumps(dict(result,known_cost_usd=float(ledger.spent),unresolved_reservations_usd=float(sum(ledger.pending.values())))))
    root_freeze=tmp_path/"root-freeze.json";root_freeze.write_text(json.dumps(frozen))
    subset=remaining_jobs(cfg,selected,cps,records(out,"branches"),records(out,"transport"))
    child=dict(frozen,approved_source_sha256={p.name:file_hash(p) for p in out.iterdir() if p.is_file()},
        root_authorization_freeze_sha256=file_hash(root_freeze),authorized_unadmitted_cells=[list(cell(r)) for r in subset])
    second=tmp_path/"second";second.mkdir();second_ledger=BudgetLedger(second/"budget.jsonl",.5)
    _,_,_,new_jobs=import_bank(out,second,second_ledger,child,authorization_root=root_freeze)
    assert new_jobs==subset and second_ledger.pending==ledger.pending and second_ledger.spent==ledger.spent
    history=json.loads((second/"recovery-continuation-history.json").read_text())
    assert len(history)==1 and (second/history[0]["path"]).read_bytes()==(out/"recovery-continuation.json").read_bytes()
    from vao.analysis import analyze_recovery_transfer as a
    assert len(a.recovery_lineages(second))==2
    (second/history[0]["path"]).write_text("tampered")
    with pytest.raises(ValueError,match="Archived recovery lineage changed"):a.recovery_lineages(second)
    (root/"branches.jsonl").write_text("tampered\n")
    other=tmp_path/"rejected";other.mkdir()
    with pytest.raises(ValueError,match="Authorized source changed"):
        import_bank(root,other,BudgetLedger(other/"budget.jsonl",.5),frozen)
