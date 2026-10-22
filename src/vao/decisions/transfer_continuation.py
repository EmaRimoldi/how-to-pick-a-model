"""Explicitly authorized transport continuation: never repeat an admitted cell."""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import digest
from .recovery import CONDITIONS, evaluate, recovery_messages
from .transfer import file_hash, load_tasks, records, reservation, source_data
from .verification import SandboxVerifier


def cell(row):
    return row["checkpoint_id"], row["model_name"], row["arm"], row["draw"]


def remaining_jobs(config, selected, checkpoints, observed, uncertain):
    """Resolve identity, never infer an unknown request's answer or billing."""
    known = {cell(r) for r in observed}
    missing = {cell(r) for r in uncertain if r["action"] == "branch"}
    if len(known) != len(observed) or known & missing:
        raise ValueError("Repeated or conflicting admitted cell")
    expected = [{"checkpoint_id": id_, "task_id": checkpoints[id_]["task_id"],
                 "action": "branch", "parent_call": checkpoints[id_]["parent_call"],
                 "model_name": m, "arm": a, "draw": d}
                for id_ in selected for m in config["target_models"]
                for a in CONDITIONS for d in range(config["branch_repeats"])]
    if not known | missing <= {cell(r) for r in expected}:
        raise ValueError("Unplanned admitted cell")
    return [r for r in expected if cell(r) not in known | missing]


def import_bank(source, output, ledger, freeze):
    """Import the immutable stopped segment, retaining every reservation once."""
    for name, expected in freeze["approved_source_sha256"].items():
        if file_hash(source/name) != expected:
            raise ValueError("Authorized source changed: "+name)
    manifest=json.loads((source/"manifest.json").read_text());cfg=manifest["config"]
    if file_hash(source/"manifest.json") != freeze["original_manifest_sha256"]:
        raise ValueError("Frozen experimental identity changed")
    summary=json.loads((source/"summary.json").read_text())
    if not summary["status"].startswith("BackendStopped: OpenRouter URLError"):
        raise ValueError("Only the explicitly authorized transport stop may continue")
    for name,expected in manifest["source_sha256"].items():
        if Path(name).name!="transfer.py" and file_hash(Path(name))!=expected:
            raise ValueError("Message, evaluator, policy or billing helper changed")
    if digest(json.loads((source/"frozen-policy.json").read_text()))!=manifest["policy_sha256"]:
        raise ValueError("Frozen weights changed")
    selected=json.loads((source/"selection.json").read_text())["selected_checkpoint_ids"]
    cps={r["checkpoint_id"]:r for r in records(source,"checkpoints")}
    branches=records(source,"branches");transport=records(source,"transport")
    jobs=remaining_jobs(cfg,selected,cps,branches,transport)
    if [cell(r) for r in jobs] != [tuple(k) for k in freeze["authorized_unadmitted_cells"]]:
        raise ValueError("Remaining requests differ from the authorized plan")
    calls=records(source,"calls");events=records(source,"budget")
    reserve={r["call"]:r for r in events if r["event"]=="reserve"}
    settled={r["call"]:r for r in events if r["event"]=="settle"}
    if set(settled)!={r["call"] for r in calls} or set(reserve)-set(settled)!={r["call"] for r in transport}:
        raise ValueError("Response, transport and billing identities do not reconcile")
    if {r["call"] for r in records(source,"evaluations")}!=set(settled):
        raise ValueError("Known responses are not all evaluated")
    for row in calls:
        if Decimal(str(row["usage"]["cost"]))!=Decimal(str(settled[row["call"]]["cost_usd"])):
            raise ValueError("Receipt/settlement mismatch")
    for event in events:
        if event["event"]=="reserve":
            if ledger.reserve(Decimal(str(event["reserved_usd"])),event["model"])!=event["call"]:
                raise ValueError("Imported admission identity changed")
        else:ledger.settle(event["call"],event["cost_usd"])
    if file_hash(output/"budget.jsonl")!=file_hash(source/"budget.jsonl"):
        raise ValueError("Imported journal bytes differ")
    for p in source.iterdir():
        if p.is_file() and p.name not in {"budget.jsonl","summary.json","checksums.json"}:
            shutil.copyfile(p,output/p.name)
    lineage={"event":"human_authorized_unadmitted_recovery_continuation",
        "created_utc":datetime.now(timezone.utc).isoformat(),"source_summary":summary,
        "source_manifest_sha256":file_hash(source/"manifest.json"),
        "source_hashes":{p.name:file_hash(p) for p in source.iterdir() if p.is_file()},
        "imported_line_counts":{p.name:len(p.read_bytes().splitlines()) for p in source.glob("*.jsonl")},
        "imported_last_admitted_call":ledger.calls,
        "censored_branch_requests":[r for r in transport if r["action"]=="branch"],
        "selected_checkpoint_ids_unchanged":selected,"authorized_unadmitted_cells":[list(cell(r)) for r in jobs],
        "authorization":freeze["authorization"],"source_collector_sha256":file_hash(Path(__file__)),
        "source_collector_git_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "interpretation":"Bank remains incomplete: do not relabel complete-case intervals confirmatory."}
    (output/"recovery-continuation.json").write_text(json.dumps(lineage,sort_keys=True,indent=2)+"\n")
    return cfg,selected,cps,jobs


def collect_unadmitted(config, selected, checkpoints, jobs, problems, donors, client, verifier, output):
    """One attempt per never-admitted cell; stop new admissions on uncertainty."""
    branches=records(output,"branches")
    done={r["checkpoint_id"] for r in records(output,"blocks")}
    lock=threading.Lock()
    block_reserve=sum(reservation(config,m)*len(CONDITIONS)*config["branch_repeats"] for m in config["target_models"])
    def score(job, call):
        scored=evaluate(problems[job["task_id"]],call,verifier)
        row={k:v for k,v in job.items() if k!="messages"}
        row.update(call=call["call"],passed=scored["heldout"]["passed"],visible_passed=scored["visible"]["passed"],incremental_cost_usd=call["cost_usd"])
        with lock:
            append_json(output/"evaluations.jsonl",{"call":call["call"],"task_id":job["task_id"],**scored})
            append_json(output/"branches.jsonl",row);branches.append(row)
    status="all_unadmitted_jobs_collected_with_censored_cells"
    try:
        for id_ in selected:
            todo=[r for r in jobs if r["checkpoint_id"]==id_]
            if not todo:continue
            # Preserve the original conservative whole-block admission rule,
            # including for a partial block whose known receipts were imported.
            if client.ledger.spent+sum(client.ledger.pending.values())+block_reserve>client.ledger.limit:
                raise BudgetStopped("Whole-block continuation gate")
            cp=checkpoints[id_];donor=donors[int(cp["task_id"].split("/")[1])%len(donors)]
            # Original shuffle over all cells; filter admissions afterwards.
            original=[{"checkpoint_id":id_,"task_id":cp["task_id"],"action":"branch","parent_call":cp["parent_call"],
                "model_name":m,"arm":a,"draw":d} for m in config["target_models"] for a in CONDITIONS for d in range(config["branch_repeats"])]
            random.Random(config["seed"]+int(id_)).shuffle(original)
            allowed={cell(r) for r in todo};queue=[]
            for i,j in enumerate(original):
                if cell(j) in allowed:
                    j.update(donor_checkpoint_id=donor["checkpoint_id"] if j["arm"]=="distractor" else None,
                        messages=recovery_messages(problems[j["task_id"]],j["arm"],cp,donor))
                    queue.append((i,j))
            error=None;scoring=[]
            with ThreadPoolExecutor(max_workers=config["workers"]) as pool,ThreadPoolExecutor(max_workers=config["verifier_workers"]) as scoring_pool:
                pending={pool.submit(client.complete,j["model_name"],j["messages"],config["seed"]+i,
                    {k:v for k,v in j.items() if k!="messages"}):j for i,j in queue}
                for future in as_completed(pending):
                    try:scoring.append(scoring_pool.submit(score,pending[future],future.result()))
                    except (BackendStopped,BudgetStopped) as exc:error=error or exc
                for future in as_completed(scoring):future.result()
            if error:raise error
            count=sum(r["checkpoint_id"]==id_ for r in branches)
            if count==len(CONDITIONS)*len(config["target_models"])*config["branch_repeats"]:
                done.add(id_);append_json(output/"blocks.jsonl",{"checkpoint_id":id_,"task_id":cp["task_id"],"event":"complete","last_admitted_call":client.ledger.calls})
            append_json(output/"continuation-blocks.jsonl",{"checkpoint_id":id_,"observed_cells":count,"complete":id_ in done,"last_admitted_call":client.ledger.calls})
            print(json.dumps({"phase":"unadmitted_recovery_continuation","complete_states":len(done),"selected_states":len(selected),"responses":len(branches),"spent_usd":float(client.ledger.spent)}),flush=True)
    except (BackendStopped,BudgetStopped) as exc:status=type(exc).__name__+": "+str(exc)
    summary={"status":status,"initial_tasks":len(records(output,"initial")),"failed_checkpoints":len(checkpoints),
        "complete_states":len(done),"selected_states":len(selected),"branch_responses":len(branches),
        "known_cost_usd":float(client.ledger.spent),"unresolved_reservations_usd":float(sum(client.ledger.pending.values())),
        "prior_campaign_upper_usd":config["prior_committed_usd"],"note":"Original cohort retained; uncertain cells never reissued, no completed-confirmatory-bank claim."}
    (output/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--freeze",type=Path,required=True);p.add_argument("--live",action="store_true")
    p.add_argument("--key-stdin",action="store_true");p.add_argument("--budget-usd",type=float)
    args=p.parse_args();frozen=json.loads(args.freeze.read_text())
    cfg=json.loads((args.source/"manifest.json").read_text())["config"]
    if args.live and (not args.key_stdin or args.budget_usd is None or not 0<args.budget_usd<=cfg["run_ceiling_usd"]
            or Decimal(str(args.budget_usd))+Decimal(str(cfg["prior_committed_usd"]))>Decimal(str(cfg["campaign_ceiling_usd"]))):
        p.error("Stdin credentials and an existing-campaign-safe cumulative cap are required")
    if file_hash(Path(__file__))!=frozen["continuation_source_sha256"]:
        p.error("Continuation collector changed after the explicit freeze")
    args.output.mkdir(parents=True,exist_ok=False)
    ledger=BudgetLedger(args.output/"budget.jsonl",args.budget_usd if args.live else cfg["run_ceiling_usd"])
    cfg,selected,cps,jobs=import_bank(args.source,args.output,ledger,frozen)
    if not args.live:
        print(json.dumps({"status":"plan_only","unadmitted_jobs":len(jobs),"imported_known_cost_usd":float(ledger.spent),"held_usd":float(sum(ledger.pending.values()))}));return 0
    key=sys.stdin.readline().strip()
    if not key:p.error("Missing stdin credential")
    problems,tasks=load_tasks(cfg)
    manifest=json.loads((args.source/"manifest.json").read_text())
    if tasks!=manifest["task_order"] or any(digest(problems[t]["prompt"])!=manifest["prompt_sha256"][t] for t in tasks):
        raise ValueError("Task prompts/order changed")
    donor_data=source_data(cfg);donors=sorted(donor_data["checkpoints"],key=lambda r:r["task_id"])
    verifier=SandboxVerifier();probe=verifier.preflight()
    client=OpenRouterClient(key,cfg,args.output,ledger);check=client.preflight()
    (args.output/"recovery-continuation-preflight.json").write_text(json.dumps({"sandbox":probe,"endpoints":check["endpoints"],"created_utc":datetime.now(timezone.utc).isoformat()},sort_keys=True,indent=2)+"\n")
    result=collect_unadmitted(cfg,selected,cps,jobs,problems,donors,client,verifier,args.output)
    print(json.dumps(result),flush=True)
    return 0 if result["status"]=="all_unadmitted_jobs_collected_with_censored_cells" else 2


if __name__=="__main__":
    raise SystemExit(main())
