"""Frozen outcome-blind semantic forecast control; separate from the primary transfer run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .context_value import parse_forecast
from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import SYSTEM, digest
from .transfer import file_hash, records


VIEWS = ("task_only", "feedback_only", "state")


def messages(prompt: str, checkpoint: dict, policy: dict, config: dict, view: str) -> list[dict]:
    """All views share instructions/priors; no recovery outcome or Plus datum is projected."""
    if view not in VIEWS:
        raise ValueError("Unknown semantic forecast view")
    payload = {"task": prompt, "previous_solver": config["models"]["producer"]["id"],
        "target_models": {m: config["models"][m]["id"] for m in config["target_models"]},
        "development_probabilities": policy["priors"], "development_mean_api_cost_usd": policy["mean_action_cost_usd"]}
    if view in {"feedback_only", "state"}:
        payload["public_base_feedback"] = checkpoint["feedback"]
    if view == "state":
        payload["previous_solution"] = checkpoint["solution"]
    instruction = ('A previous Python solution failed public base tests. Predict the probability that ONE '
        'next solution passes BOTH public base and evaluation-only additional tests. No additional-test '
        'outcomes are available. fresh receives only the task; artifact also gets previous code; '
        'feedback also gets public test feedback; artifact_feedback gets both. Use the supplied '
        'development estimates as priors, adjusting for the task and any available state. '
        'Return only {"probabilities": {"MODEL.ARM": NUMBER, ...}} with numbers in [0,1] '
        'for exactly these keys: ' + json.dumps([m+"."+a for m in config["target_models"]
            for a in ("fresh","artifact","feedback","artifact_feedback")]))
    return [{"role":"system","content":instruction},{"role":"user","content":json.dumps(payload,sort_keys=True)}]


def public_inputs(root: Path) -> dict:
    """Read only public checkpoint fields, initial prompts, frozen weights and billing."""
    manifest = json.loads((root/"manifest.json").read_text())
    policy = json.loads((root/"frozen-policy.json").read_text())
    selected = json.loads((root/"selection.json").read_text())["selected_checkpoint_ids"]
    cps = {r["checkpoint_id"]: r for r in records(root,"checkpoints")}
    prompts = {}
    # Stream and discard all non-initial rows; never load evaluations/branch labels.
    with (root/"calls.jsonl").open() as f:
        for line in f:
            row = json.loads(line)
            if row["action"] != "initial":
                continue
            content = row["messages"][0]["content"]
            if not content.startswith(SYSTEM+"\n\n"):
                raise ValueError("Unexpected producer prompt")
            prompts[row["task_id"]] = content[len(SYSTEM+"\n\n"):]
    ledger=records(root,"budget")
    reserves={r["call"]:Decimal(str(r["reserved_usd"])) for r in ledger if r["event"]=="reserve"}
    settlements={r["call"]:Decimal(str(r["cost_usd"])) for r in ledger if r["event"]=="settle"}
    total = Decimal(str(manifest["config"]["prior_committed_usd"])) + sum(settlements.values()) + sum(v for k,v in reserves.items() if k not in settlements)
    if not (root/"summary.json").exists():
        raise ValueError("Primary collection still active; no concurrent overlapping budgets")
    return {"manifest":manifest,"policy":policy,"checkpoints":[cps[i] for i in selected],"prompts":prompts,"prior_upper":total}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--budget-usd",type=float)
    parser.add_argument("--key-stdin",action="store_true")
    args=parser.parse_args()
    public=public_inputs(args.input)
    config=public["manifest"]["config"]
    freeze_path=Path("experiments/mbpp-plus/context-value-transfer/configs/semantic-control-freeze.json")
    frozen=json.loads(freeze_path.read_text())
    if (file_hash(Path(__file__)) != frozen["source_file_sha256"]
            or file_hash(args.input/"manifest.json") != frozen["source_primary_manifest_sha256"]
            or frozen["target_responses_at_freeze_check"] != 0):
        raise ValueError("Semantic control differs from its pre-recovery freeze")
    cap=min(Decimal("0.08"),Decimal(str(config["campaign_ceiling_usd"]))-public["prior_upper"])
    args.output.mkdir(parents=True,exist_ok=False)
    manifest={"kind":"prespecified_outcome_blind_semantic_control","created_utc":datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256":file_hash(args.input/"manifest.json"), "source_policy_sha256":digest(public["policy"]),
        "source_file_sha256":file_hash(Path(__file__)),"prior_upper_usd":float(public["prior_upper"]),
        "semantic_freeze_sha256":file_hash(freeze_path),
        "maximum_new_budget_usd":float(cap),"config":config,
        "git_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "prediction_timing":"after primary collection; prompt/config fixed before any target recovery outcome"}
    (args.output/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    if not args.live:
        print(json.dumps({"status":"plan_only","states":len(public["checkpoints"]),"maximum_new_budget_usd":float(cap)}))
        return 0
    if not args.key_stdin or args.budget_usd is None or not 0<Decimal(str(args.budget_usd))<=cap:
        parser.error("Declare a stdin key and a budget within the remaining campaign cap and $0.08")
    key=sys.stdin.readline().strip()
    if not key:
        parser.error("Missing stdin key")
    ledger=BudgetLedger(args.output/"budget.jsonl",args.budget_usd)
    forecast_config=dict(config,models={"small":config["models"]["small"]})
    client=OpenRouterClient(key,forecast_config,args.output,ledger)
    manifest["endpoints"]=client.preflight()["endpoints"]
    (args.output/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    jobs=[(cp,view) for cp in public["checkpoints"] for view in VIEWS]
    completed,valid=0,0
    status="complete"
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(client.complete,"small",messages(public["prompts"][cp["task_id"]],cp,public["policy"],config,view),
            config["seed"],{"action":"forecast","model_name":"small","task_id":cp["task_id"],"checkpoint_id":cp["checkpoint_id"],"view":view}):(cp,view) for cp,view in jobs}
        for future in as_completed(pending):
            cp,view=pending[future]
            try:
                call=future.result()
            except (BudgetStopped,BackendStopped) as exc:
                status=type(exc).__name__+": "+str(exc)
                continue
            probabilities,ok=parse_forecast(call,config)
            append_json(args.output/"predictions.jsonl",{"call":call["call"],"task_id":cp["task_id"],"checkpoint_id":cp["checkpoint_id"],
                "view":view,"probabilities":probabilities,"valid":ok,"cost_usd":call["cost_usd"]})
            completed+=1;valid+=ok
            if completed%25==0:
                print(json.dumps({"completed":completed,"total":len(jobs),"spent_usd":float(ledger.spent)}),flush=True)
    result={"status":status,"forecasts":completed,"valid":valid,"known_cost_usd":float(ledger.spent),
        "unresolved_reservations_usd":float(sum(ledger.pending.values())),"prior_upper_usd":float(public["prior_upper"])}
    (args.output/"summary.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result),flush=True)
    return 0 if status=="complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
