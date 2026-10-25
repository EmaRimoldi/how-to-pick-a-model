"""Prospective cross-benchmark recovery replication, with a fixed source-trained policy."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

from .context_value import ARMS
from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import SYSTEM, digest
from .recovery import CONDITIONS, evaluate, producer_messages, recovery_messages
from .recovery_policy import TASK_FEATURES, STATE_FEATURES, fit_policy, predict
from .verification import SandboxVerifier


FEEDBACK_FEATURES = TASK_FEATURES + tuple(n for n in STATE_FEATURES if n not in TASK_FEATURES
    and n not in {"log_code_characters", "log_ast_nodes", "syntax_valid"})
VIEWS = {"task": TASK_FEATURES, "feedback": FEEDBACK_FEATURES, "state": STATE_FEATURES}


def records(root: Path, name: str) -> list[dict]:
    path = root / (name + ".jsonl")
    return [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reservation(config: dict, model: str) -> Decimal:
    m = config["models"][model]
    return (Decimal(str(config["input_token_ceiling"])) * Decimal(str(m["input_per_million"]))
            + Decimal(str(config["max_tokens"])) * Decimal(str(m["output_per_million"]))) / 1_000_000


def source_data(config: dict) -> dict:
    """The entire previous evaluation is now explicitly training data, never a new holdout."""
    root = Path(config["training_source"])
    hashes = json.loads((root / "checksums.json").read_text())
    for name in ("calls.jsonl", "branches.jsonl", "checkpoints.jsonl", "initial.jsonl"):
        if file_hash(root / name) != hashes[name]:
            raise ValueError("Training source checksum changed: " + name)
    analysis_path = root / "analysis.json"
    if file_hash(analysis_path) != hashes["analysis.json"]:
        raise ValueError("Prior accounting checksum changed")
    prior = json.loads(analysis_path.read_text())["collection"]
    upper = sum(Decimal(str(prior[k])) for k in ("collection_cost_usd", "prior_committed_usd", "unresolved_reserved_usd"))
    if "prior_committed_usd" in config and Decimal(str(config["prior_committed_usd"])) < upper:
        raise ValueError("Prior campaign spend/reservations would be understated")
    checkpoints = records(root, "checkpoints")
    calls = {r["call"]: r for r in records(root, "calls")}
    prompts = {}
    for cp in checkpoints:
        content = calls[cp["parent_call"]]["messages"][0]["content"]
        if not content.startswith(SYSTEM + "\n\n"):
            raise ValueError("Unexpected source producer prompt")
        prompts[cp["task_id"]] = content[len(SYSTEM + "\n\n"):]
    branches = [r for r in records(root, "branches") if r["action"] == "branch"]
    policy = fit_policy(checkpoints, branches, prompts, dict(config, branch_repeats=2), views=VIEWS)
    policy["source_hashes"] = {n: hashes[n] for n in ("calls.jsonl", "branches.jsonl", "checkpoints.jsonl", "initial.jsonl")}
    return {"policy": policy, "checkpoints": checkpoints, "branches": branches,
            "initial": records(root, "initial"), "prompts": prompts, "calls": calls}


def choose(policy: dict, probabilities: dict, config: dict, budget: float, prefix: float,
           restriction: str | None = None) -> str | None:
    """No realized future bill or hidden success is an admission/selection input."""
    keys = [m + "." + a for m in config["target_models"] for a in ARMS]
    if restriction == "model_only":
        keys = [k for k in keys if k.endswith(".artifact_feedback")]
    keys = [k for k in keys if Decimal(str(prefix)) + reservation(config, k.split(".")[0]) <= Decimal(str(budget))]
    if not keys:
        return None
    selected = max(keys, key=lambda k: config["solution_value_usd"] * probabilities[k] - policy["mean_action_cost_usd"][k])
    if config["solution_value_usd"] * probabilities[selected] <= policy["mean_action_cost_usd"][selected]:
        return None
    return selected


def replay(rows: list[dict], action: str | None, prefix: float, config: dict, budget: float,
           *, include_prefix: bool = True) -> dict:
    """Two observed draws, fixed action, stop on public pass, advance reservations."""
    spent = Decimal(str(prefix)) if include_prefix else Decimal(0)
    if action is None:
        return {"passed": False, "cost_usd": float(spent), "attempts": 0, "termination": "abstain"}
    model, arm = action.split(".")
    candidates = sorted((r for r in rows if r["model_name"] == model and r["arm"] == arm), key=lambda r: r["draw"])
    if len(candidates) < config["maximum_attempts"]:
        raise ValueError("Unobserved action in replay")
    passed, attempts, reason = False, 0, "budget"
    for r in candidates[:config["maximum_attempts"]]:
        if spent + reservation(config, model) > Decimal(str(budget)):
            break
        spent += Decimal(str(r["incremental_cost_usd"]))
        attempts += 1
        reason = "attempt_cap"
        if r["visible_passed"]:
            passed, reason = r["passed"], "public_pass"
            break
    if spent > Decimal(str(budget)):
        raise ValueError("Replay overspend")
    return {"passed": passed, "cost_usd": float(spent), "attempts": attempts, "termination": reason}


def freeze(config: dict) -> tuple[dict, dict]:
    data = source_data(config)
    policy = data["policy"]
    fixed = {}
    for budget in config["task_budgets_usd"]:
        scores = {}
        for action in policy["priors"]:
            values = []
            for cp in data["checkpoints"]:
                rows = [r for r in data["branches"] if r["checkpoint_id"] == cp["checkpoint_id"]]
                outcome = replay(rows, action, cp["prefix_cost_usd"], config, budget)
                values.append(config["solution_value_usd"] * outcome["passed"] - outcome["cost_usd"])
            scores[action] = sum(values) / len(values)
        fixed[str(budget)] = max(scores, key=scores.get)
    policy["development_replay_fixed"] = fixed
    return policy, data


def load_tasks(config: dict) -> tuple[dict, list[str]]:
    from evalplus.data import get_mbpp_plus, get_mbpp_plus_hash
    if importlib.metadata.version("evalplus") != "0.3.1" or get_mbpp_plus_hash() != config["dataset_hash"]:
        raise ValueError("Pinned MBPP+/EvalPlus changed")
    audit = Path(config["reference_audit"])
    if file_hash(audit) != config["reference_audit_sha256"]:
        raise ValueError("Reference preflight changed")
    observed = [json.loads(s) for s in audit.read_text().splitlines()]
    problems = {t: dict(p, dataset="mbpp") for t, p in get_mbpp_plus().items()}
    if len(observed) != len(problems) or {r["task_id"] for r in observed} != set(problems):
        raise ValueError("Reference census incomplete")
    excluded = [r["task_id"] for r in observed if not r["base_feedback"]["passed"] or not r["heldout"]["passed"]]
    if sorted(excluded) != sorted(config["reference_exclusions"]):
        raise ValueError("Reference exclusions differ from frozen config")
    tasks = sorted(set(problems) - set(excluded), key=lambda t: int(t.split("/")[1]))
    random.Random(config["seed"]).shuffle(tasks)
    return problems, tasks


def import_prefixes(source: Path, output: Path, ledger: BudgetLedger, config: dict,
                    policy: dict, tasks: list[str]) -> dict:
    """Explicit pre-bank transport continuation; never regenerate the unknown prefix.

    A late missing prefix cannot change the first N failures if N were already
    fully observed before it. Preserve the original experimental manifest and
    record the new collector/preflight separately as engineering lineage.
    """
    manifest=json.loads((source/"manifest.json").read_text())
    summary=json.loads((source/"summary.json").read_text())
    calls=records(source,"calls");initial=records(source,"initial");cps=records(source,"checkpoints")
    if (manifest["config"]!=config or manifest["task_order"]!=tasks
            or not summary["status"].startswith("BackendStopped: OpenRouter URLError")
            or records(source,"branches") or records(source,"local-predictions")
            or any(c["action"]!="initial" for c in calls)
            or len(calls)!=len(initial) or len(cps)<config["maximum_checkpoints"]
            or (source/"prefix-continuation.json").exists()):
        raise ValueError("Only the explicit late-prefix transport stop with a complete selected cohort may continue")
    for relative,expected in manifest["source_sha256"].items():
        if Path(relative).name!="transfer.py" and file_hash(Path(relative))!=expected:
            raise ValueError("Evaluator, policy, messages or billing transport changed")
    if json.loads((source/"frozen-policy.json").read_text())!=policy:
        raise ValueError("Frozen weights changed")
    events=records(source,"budget")
    reserved={r["call"]:r for r in events if r["event"]=="reserve"}
    settled={r["call"]:r for r in events if r["event"]=="settle"}
    unknown=set(reserved)-set(settled)
    transport=records(source,"transport")
    if (len(unknown)!=1 or len(transport)!=1 or transport[0]["call"] not in unknown
            or transport[0]["action"]!="initial" or transport[0]["model_name"]!="producer"
            or transport[0]["task_id"]!=tasks[len(initial)]
            or [r["task_id"] for r in initial]!=tasks[:len(initial)]
            or set(settled)!={r["call"] for r in calls}):
        raise ValueError("Unknown prefix identity/order is not uniquely preserved")
    missing=transport[0]
    selected=cps[:config["maximum_checkpoints"]]
    if any(tasks.index(c["task_id"])>=tasks.index(missing["task_id"]) for c in selected):
        raise ValueError("Missing prefix could change the selected recovery population")
    for call in calls:
        if Decimal(str(call["usage"]["cost"]))!=Decimal(str(settled[call["call"]]["cost_usd"])):
            raise ValueError("Known receipt mismatch")
    if len(records(source,"evaluations"))!=len(calls):
        raise ValueError("Known prefix evaluations are incomplete")
    for event in events:
        if event["event"]=="reserve":
            if (Decimal(str(event["reserved_usd"]))!=reservation(config,"producer")
                    or event["model"]!=config["models"]["producer"]["id"]):
                raise ValueError("Prefix reservation differs from the frozen provider/model ceiling")
            if ledger.reserve(Decimal(str(event["reserved_usd"])),event["model"])!=event["call"]:
                raise ValueError("Imported admission sequence changed")
        else:
            ledger.settle(event["call"],event["cost_usd"])
    for name in ("calls.jsonl","initial.jsonl","checkpoints.jsonl","evaluations.jsonl","transport.jsonl","frozen-policy.json","manifest.json"):
        shutil.copyfile(source/name,output/name)
    provenance={"event":"explicit_late_prefix_continuation","created_utc":datetime.now(timezone.utc).isoformat(),
        "source_manifest_sha256":file_hash(source/"manifest.json"),"source_summary":summary,
        "source_hashes":{n:file_hash(source/n) for n in ("calls.jsonl","initial.jsonl","checkpoints.jsonl","evaluations.jsonl","budget.jsonl","transport.jsonl")},
        "imported_observed_prefixes":len(initial),"censored_prefix":missing,
        "imported_budget_events":len(events),"imported_checkpoints":len(cps),
        "selected_checkpoint_ids_unchanged":[c["checkpoint_id"] for c in selected],
        "new_collector_git_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "new_collector_sha256":file_hash(Path(__file__)),
        "manifest_note":"manifest.json remains the original frozen experimental identity; this file records the continuation implementation."}
    (output/"prefix-continuation.json").write_text(json.dumps(provenance,sort_keys=True,indent=2)+"\n")
    return {"initial":initial,"checkpoints":cps,"censored_tasks":[missing["task_id"]]}


def collect(config: dict, tasks: list[str], problems: dict, policy: dict, source: dict,
            client: OpenRouterClient, verifier: SandboxVerifier, output: Path, prefixes: dict | None = None) -> dict:
    """No automatic retries/resume; keep every response and every unresolved admission."""
    initial, checkpoints, branches = (list(prefixes["initial"]),list(prefixes["checkpoints"]),[]) if prefixes else ([],[],[])
    censored=prefixes["censored_tasks"] if prefixes else []

    score_lock = threading.Lock()

    def record_score(job: dict, call: dict, scored: dict) -> dict:
        append_json(output / "evaluations.jsonl", {"call": call["call"], "task_id": job["task_id"], **scored})
        if job["action"] == "initial":
            row = {"task_id": job["task_id"], "call": call["call"], "passed": scored["heldout"]["passed"],
                   "visible_passed": scored["visible"]["passed"], "cost_usd": call["cost_usd"]}
            initial.append(row)
            append_json(output / "initial.jsonl", row)
            if not row["visible_passed"]:
                cp = {"checkpoint_id": str(call["call"]), "task_id": row["task_id"], "parent_call": call["call"],
                      "solution": scored["solution"], "solution_sha256": scored["solution_sha256"],
                      "feedback": scored["visible"], "prefix_cost_usd": call["cost_usd"]}
                checkpoints.append(cp)
                append_json(output / "checkpoints.jsonl", cp)
        else:
            row = {k: v for k, v in job.items() if k != "messages"}
            row.update(call=call["call"], passed=scored["heldout"]["passed"], visible_passed=scored["visible"]["passed"],
                       incremental_cost_usd=call["cost_usd"])
            branches.append(row)
            append_json(output / "branches.jsonl", row)
        return row

    def score(job: dict, call: dict) -> dict:
        scored = evaluate(problems[job["task_id"]], call, verifier)
        with score_lock:
            return record_score(job, call, scored)

    status = "complete"
    try:
        done={r["task_id"] for r in initial}|set(censored)
        for t in (t for t in tasks if t not in done):
            job = {"task_id": t, "action": "initial", "model_name": "producer", "messages": producer_messages(problems[t])}
            call = client.complete("producer", job["messages"], config["seed"], {k: v for k,v in job.items() if k != "messages"})
            score(job, call)
            if len(initial) == 3 and all(c["feedback"]["status"] == "format_error" for c in checkpoints) and len(checkpoints) == 3:
                raise BackendStopped("All three smoke prefixes malformed")
            if len(initial) % 25 == 0:
                print(json.dumps({"phase": "prefix", "completed": len(initial), "failures": len(checkpoints), "spent_usd": float(client.ledger.spent)}), flush=True)
        selected = checkpoints[:config["maximum_checkpoints"]]
        (output / "selection.json").write_text(json.dumps({"selected_checkpoint_ids": [c["checkpoint_id"] for c in selected],
            "all_failed_checkpoints": len(checkpoints), "last_admitted_call": client.ledger.calls}, indent=2) + "\n")
        # Save all predictions before the first target-model request, including states
        # which may subsequently remain unmeasured because the budget gate stops.
        for cp in selected:
            append_json(output / "local-predictions.jsonl", {"task_id": cp["task_id"], "checkpoint_id": cp["checkpoint_id"],
                "policy_sha256": digest(policy), "last_admitted_call": client.ledger.calls,
                "probabilities": {v: predict(policy, problems[cp["task_id"]]["prompt"], cp, v) for v in ("global", *VIEWS)}})
        donors = sorted(source["checkpoints"], key=lambda c: c["task_id"])
        complete = 0
        block_reserve = sum(reservation(config, m) * len(CONDITIONS) * config["branch_repeats"] for m in config["target_models"])
        for cp in selected:
            # Only admit complete matched blocks. This gate cannot see this state's
            # branch outcomes; preserve selected-but-unmeasured states for bounds.
            if client.ledger.spent + sum(client.ledger.pending.values()) + block_reserve > client.ledger.limit:
                status = "budget_block_gate"
                break
            donor = donors[int(cp["task_id"].split("/")[1]) % len(donors)]
            jobs = [{"task_id": cp["task_id"], "action": "branch", "model_name": m, "arm": a, "draw": d,
                     "checkpoint_id": cp["checkpoint_id"], "parent_call": cp["parent_call"],
                     "donor_checkpoint_id": donor["checkpoint_id"] if a == "distractor" else None,
                     "messages": recovery_messages(problems[cp["task_id"]], a, cp, donor)}
                    for m in config["target_models"] for a in CONDITIONS for d in range(config["branch_repeats"])]
            random.Random(config["seed"] + int(cp["checkpoint_id"])).shuffle(jobs)
            error = None
            scored_futures = []
            with ThreadPoolExecutor(max_workers=config["workers"]) as pool, ThreadPoolExecutor(
                    max_workers=config["verifier_workers"]) as scoring_pool:
                pending = {pool.submit(client.complete, j["model_name"], j["messages"], config["seed"] + i,
                    {k: v for k, v in j.items() if k != "messages"}): j for i, j in enumerate(jobs)}
                for future in as_completed(pending):
                    try:
                        call = future.result()
                        scored_futures.append(scoring_pool.submit(score, pending[future], call))
                    except (BudgetStopped, BackendStopped) as exc:
                        error = error or exc
                for future in as_completed(scored_futures):
                    future.result()
            if error:
                raise error
            complete += 1
            append_json(output / "blocks.jsonl", {"checkpoint_id": cp["checkpoint_id"], "task_id": cp["task_id"],
                "event": "complete", "last_admitted_call": client.ledger.calls})
            print(json.dumps({"phase": "matched_bank", "complete_states": complete, "selected_states": len(selected),
                              "responses": len(branches), "spent_usd": float(client.ledger.spent)}), flush=True)
    except (BudgetStopped, BackendStopped) as exc:
        status = type(exc).__name__ + ": " + str(exc)
    if status=="complete" and censored:
        status="complete_with_censored_prefix"
    summary = {"status": status, "initial_tasks": len(initial), "failed_checkpoints": len(checkpoints),
        "branch_responses": len(branches), "known_cost_usd": float(client.ledger.spent),
        "unresolved_reservations_usd": float(sum(client.ledger.pending.values())),
        "prior_campaign_upper_usd": config["prior_committed_usd"],"censored_initial_tasks":censored}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--key-stdin", action="store_true")
    parser.add_argument("--continue-prefix-from",type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.live and (not args.key_stdin or args.budget_usd is None or args.budget_usd <= 0
            or Decimal(str(args.budget_usd)) > Decimal(str(config["run_ceiling_usd"]))
            or Decimal(str(args.budget_usd)) + Decimal(str(config["prior_committed_usd"])) > Decimal(str(config["campaign_ceiling_usd"]))):
        parser.error("Live collection needs stdin key and a declared cumulative-safe budget")
    problems, tasks = load_tasks(config)
    policy, source = freeze(config)
    if digest(policy) != config["source_policy_digest"]:
        raise ValueError("Source policy differs from the prospectively committed weights")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "frozen-policy.json").write_text(json.dumps(policy, sort_keys=True, indent=2) + "\n")
    manifest = {"config": config, "task_order": tasks, "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "created_utc": datetime.now(timezone.utc).isoformat(), "policy_sha256": digest(policy),
        "prompt_sha256": {t: digest(problems[t]["prompt"]) for t in tasks}, "policy_frozen_before_calls": True}
    manifest["source_sha256"] = {"src/vao/decisions/" + p.name: file_hash(p) for p in [Path(__file__),
        Path(__file__).with_name("verifier_worker.py"), Path(__file__).with_name("verification.py"),
        Path(__file__).with_name("recovery_policy.py"), Path(__file__).with_name("recovery.py"),
        Path(__file__).with_name("openrouter.py")]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if not args.live:
        print(json.dumps({"status": "plan_only", "tasks": len(tasks), "training_states": len(source["checkpoints"]),
                          "fixed": policy["development_replay_fixed"]}))
        return 0
    key = sys.stdin.readline().strip()
    if not key:
        parser.error("Missing stdin key")
    ledger = BudgetLedger(args.output / "budget.jsonl", args.budget_usd)
    prefixes=None
    if args.continue_prefix_from:
        prefixes=import_prefixes(args.continue_prefix_from,args.output,ledger,config,policy,tasks)
    verifier = SandboxVerifier()
    probe=verifier.preflight()
    client = OpenRouterClient(key, config, args.output, ledger)
    preflight = client.preflight()
    # Curatable manifest: never persist personal balances/keys.
    if prefixes:
        (args.output/"continuation-preflight.json").write_text(json.dumps({"sandbox":probe,"endpoints":preflight["endpoints"],
            "created_utc":datetime.now(timezone.utc).isoformat()},sort_keys=True,indent=2)+"\n")
    else:
        manifest.update(sandbox=probe,endpoints=preflight["endpoints"])
        (args.output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    result = collect(config, tasks, problems, policy, source, client, verifier, args.output,prefixes)
    print(json.dumps(result), flush=True)
    return 0 if result["status"].startswith("complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
