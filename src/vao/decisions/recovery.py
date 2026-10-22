"""Task-held-out recovery collection with public base feedback and frozen policies."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .context_value import ARMS, parse_forecast
from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import SYSTEM, digest
from .recovery_policy import features, fit_policy, predict
from .recovery_import import ImportedClient, continue_frozen_development, import_completed, records
from .verification import SandboxVerifier


CONDITIONS = (*ARMS, "distractor")


def load_experiment(config: dict) -> tuple[dict, dict]:
    """Validate the frozen source/split before any calls; never choose tasks by model outcomes."""
    from evalplus.data import get_human_eval_plus, get_human_eval_plus_hash
    if importlib.metadata.version("evalplus") != "0.3.1" or get_human_eval_plus_hash() != config["dataset_hash"]:
        raise ValueError("Pinned evaluator or dataset changed")
    path = Path(config["split_file"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != config["split_sha256"]:
        raise ValueError("Frozen split changed")
    split = json.loads(path.read_text())
    groups = [set(split[k]) for k in ("development_task_ids", "evaluation_task_ids", "reserved_task_ids", "reference_exclusions")]
    if any(groups[i] & groups[j] for i in range(4) for j in range(i)):
        raise ValueError("Task split overlap")
    return get_human_eval_plus(), split


def producer_messages(problem: dict) -> list[dict]:
    """Gemma uses an explicit user-only instruction; all prefixes follow this template."""
    return [{"role": "user", "content": SYSTEM + "\n\n" + problem["prompt"]}]


def resized(text: str, length: int) -> str:
    """Match character length; token differences remain measured, not assumed away."""
    return text[:length].ljust(length)


def recovery_messages(problem: dict, arm: str, checkpoint: dict | None = None,
                      donor: dict | None = None) -> list[dict]:
    """Project only the declared public task/artifact/feedback into next-solver requests."""
    if arm not in CONDITIONS:
        raise ValueError("Unknown condition")
    code, feedback = None, None
    if arm != "fresh":
        if checkpoint is None:
            raise ValueError("Missing checkpoint")
        if arm in {"artifact", "artifact_feedback", "distractor"}:
            code = checkpoint["solution"]
        if arm in {"feedback", "artifact_feedback", "distractor"}:
            feedback = json.dumps(checkpoint["feedback"], sort_keys=True)
        if arm == "distractor":
            if donor is None or donor["task_id"] == checkpoint["task_id"]:
                raise ValueError("Distractor must come from a different development task")
            code = resized(donor["solution"], len(code))
            feedback = resized(json.dumps(donor["feedback"], sort_keys=True), len(feedback))
    payload = {"task": problem["prompt"], "previous_solution": code, "public_test_feedback": feedback}
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content":
        "Solve this task. You may use, revise or discard supplied code and public test feedback. "
        "Return a complete solution.\n" + json.dumps(payload, sort_keys=True)}]


def forecast_messages(problem: dict, view: str, checkpoint: dict, policy: dict, config: dict) -> list[dict]:
    """Use equal development priors in both prospective API forecast views."""
    if view not in {"task_only", "state"}:
        raise ValueError("Unknown forecast view")
    payload = {"task": problem["prompt"], "previous_solver": config["models"][config["producer"]]["id"],
               "target_models": {m: config["models"][m]["id"] for m in config["target_models"]},
               "development_probabilities": policy["priors"], "development_mean_api_cost_usd": policy["mean_action_cost_usd"]}
    if view == "state":
        payload.update(previous_solution=checkpoint["solution"], public_base_feedback=checkpoint["feedback"])
    instruction = ('A previous Python solution failed public base tests. Predict the probability that ONE '
        'next solution passes BOTH public base and evaluation-only additional tests. No additional-test '
        'outcomes are available. fresh receives only the task; artifact also gets previous code; '
        'feedback also gets public test feedback; artifact_feedback gets both. Use the supplied '
        'development estimates as priors, adjusting for the task and any available state. '
        'Return only {"probabilities": {"MODEL.ARM": NUMBER, ...}} with numbers in [0,1] '
        'for exactly these keys: ' + json.dumps(list(policy["priors"])))
    return [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(payload, sort_keys=True)}]


def evaluate(problem: dict, call: dict, verifier: SandboxVerifier) -> dict:
    """The new public-base regime never reuses Plus outcomes as feedback."""
    start = time.perf_counter()
    try:
        source = json.loads(call["content"])["solution"]
        if call["finish_reason"] != "stop" or not isinstance(source, str) or not source.strip():
            raise ValueError("Malformed or incomplete solution")
    except (ValueError, TypeError, KeyError):
        source = ""
        visible = {"passed": False, "status": "format_error", "feedback": "Return JSON with a complete solution string"}
        heldout = {"passed": False, "status": "format_error"}
    else:
        visible = verifier.check(problem, source, "base_feedback")
        heldout = verifier.check(problem, source, "heldout")
    return {"solution": source, "solution_sha256": digest(source), "visible": visible, "heldout": heldout,
            "verifier_seconds": time.perf_counter() - start}


def run(config: dict, problems: dict, split: dict, client: OpenRouterClient,
        verifier: SandboxVerifier, output: Path, development: dict | None = None) -> dict:
    """Finish development, freeze weights, then start untouched evaluation calls."""
    checkpoints, branches, predictions, initial, evaluations = [], [], [], [], []
    if development:
        initial, checkpoints, branches, evaluations = (development[k] for k in ("initial", "checkpoints", "branches", "evaluations"))
    status = "complete"

    def batch(jobs: list[dict], workers: int | None = None) -> list[dict]:
        jobs = list(jobs)
        random.Random(config["seed"] + len(initial) + len(branches)).shuffle(jobs)
        complete = []
        error = None
        with ThreadPoolExecutor(max_workers=workers or config["workers"]) as pool:
            pending = {pool.submit(client.complete, j["model_name"], j["messages"], config["seed"] + i,
                {k: v for k, v in j.items() if k not in {"messages", "model_name"}} | {"model_name": j["model_name"]}): j
                for i, j in enumerate(jobs)}
            for future in as_completed(pending):
                job = pending[future]
                try:
                    call = future.result()
                except (BudgetStopped, BackendStopped) as exc:
                    error = error or exc
                    continue
                if job["action"] == "forecast":
                    probabilities, valid = parse_forecast(call, config)
                    row = {"call": call["call"], **{k: job[k] for k in ("task_id", "checkpoint_id", "parent_call", "split", "view")},
                           "probabilities": probabilities, "valid": valid, "cost_usd": call["cost_usd"]}
                    append_json(output / "predictions.jsonl", row)
                    predictions.append(row)
                    complete.append(row)
                    continue
                cached = getattr(client, "cached_evaluation", lambda _: None)(call["call"])
                scored = ({k: cached[k] for k in ("solution", "solution_sha256", "visible", "heldout", "verifier_seconds")}
                          if cached else evaluate(problems[job["task_id"]], call, verifier))
                record = {"call": call["call"], "task_id": job["task_id"], "split": job["split"], **scored}
                append_json(output / "evaluations.jsonl", record)
                evaluations.append(record)
                if job["action"] == "initial":
                    row = {"task_id": job["task_id"], "split": job["split"], "call": call["call"],
                           "passed": scored["heldout"]["passed"], "visible_passed": scored["visible"]["passed"], "cost_usd": call["cost_usd"]}
                    append_json(output / "initial.jsonl", row)
                    initial.append(row)
                    if not scored["visible"]["passed"]:
                        cp = {"checkpoint_id": str(call["call"]), "parent_call": call["call"], "task_id": job["task_id"],
                            "split": job["split"], "solution": scored["solution"], "solution_sha256": scored["solution_sha256"],
                            "feedback": scored["visible"], "prefix_cost_usd": call["cost_usd"]}
                        append_json(output / "checkpoints.jsonl", cp)
                        checkpoints.append(cp)
                    complete.append(row)
                else:
                    row = {k: job[k] for k in ("task_id", "split", "action", "model_name", "arm", "draw")}
                    row.update(call=call["call"], checkpoint_id=job.get("checkpoint_id"), parent_call=job.get("parent_call"),
                               donor_checkpoint_id=job.get("donor_checkpoint_id"), passed=scored["heldout"]["passed"],
                               visible_passed=scored["visible"]["passed"], incremental_cost_usd=call["cost_usd"])
                    append_json(output / "branches.jsonl", row)
                    branches.append(row)
                    complete.append(row)
                if len(complete) % 25 == 0:
                    print(json.dumps({"split": job["split"], "phase": job["action"], "batch_completed": len(complete),
                        "batch_total": len(jobs), "spent_usd": float(client.ledger.spent)}), flush=True)
        if error:
            raise error
        return complete

    def prefix_jobs(task_ids, label):
        return [{"task_id": task, "split": label, "action": "initial", "model_name": config["producer"],
                 "messages": producer_messages(problems[task])} for task in task_ids]

    def branch_jobs(states, development_states):
        jobs = []
        for cp in states:
            donors = sorted([d for d in development_states if d["task_id"] != cp["task_id"]], key=lambda d: d["task_id"])
            if not donors:
                raise ValueError("No independent development distractor")
            donor = donors[int(cp["task_id"].split("/")[1]) % len(donors)]
            for model in config["target_models"]:
                for arm in CONDITIONS:
                    for draw in range(config["branch_repeats"]):
                        jobs.append({"task_id": cp["task_id"], "split": cp["split"], "action": "branch", "model_name": model,
                            "arm": arm, "draw": draw, "checkpoint_id": cp["checkpoint_id"], "parent_call": cp["parent_call"],
                            "donor_checkpoint_id": donor["checkpoint_id"] if arm == "distractor" else None,
                            "messages": recovery_messages(problems[cp["task_id"]], arm, cp, donor)})
        return jobs

    try:
        if development:
            dev_states = sorted(checkpoints, key=lambda c: c["task_id"])
            policy = development["policy"]
            append_json(output / "phases.jsonl", {"event": "explicit_evaluation_continuation",
                "policy_sha256": digest(policy), "last_admitted_call": client.ledger.calls})
        else:
            dev_ids = split["development_task_ids"]
            batch(prefix_jobs(dev_ids[:3], "development"))
            if all(e["visible"]["status"] == "format_error" for e in evaluations):
                raise BackendStopped("All three smoke outputs malformed; inspect before further spending")
            batch(prefix_jobs(dev_ids[3:], "development"))
            dev_states = sorted(checkpoints, key=lambda c: c["task_id"])
            if len(dev_states) < config["minimum_development_failed_tasks"]:
                raise BackendStopped("Development failure coverage below the frozen fitting gate")
            batch(branch_jobs(dev_states, dev_states))
            policy = fit_policy(dev_states, branches, {t: p["prompt"] for t, p in problems.items()}, config)
            policy.update(training_branches_sha256=digest(branches), collector_git_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
            (output / "frozen-policy.json").write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")
            append_json(output / "phases.jsonl", {"event": "policy_frozen", "policy_sha256": digest(policy),
                "last_admitted_call": client.ledger.calls, "created_utc": datetime.now(timezone.utc).isoformat()})
            print(json.dumps({"phase": "policy_frozen", "development_failed_tasks": len(dev_states),
                              "spent_usd": float(client.ledger.spent)}), flush=True)
        batch(prefix_jobs(split["evaluation_task_ids"], "evaluation"), workers=1 if development else None)
        test_states = [c for c in checkpoints if c["split"] == "evaluation"]
        forecasts = []
        for cp in test_states:
            for view in ("task_only", "state"):
                forecasts.append({"task_id": cp["task_id"], "split": "evaluation", "action": "forecast", "view": view,
                    "model_name": "small", "checkpoint_id": cp["checkpoint_id"], "parent_call": cp["parent_call"],
                    "messages": forecast_messages(problems[cp["task_id"]], view, cp, policy, config)})
        batch(forecasts)
        for cp in test_states:
            row = {"checkpoint_id": cp["checkpoint_id"], "task_id": cp["task_id"],
                   "policy_sha256": digest(policy), "last_admitted_call": client.ledger.calls,
                   "probabilities": {view: predict(policy, problems[cp["task_id"]]["prompt"], cp, view) for view in ("global", "task", "state")}}
            append_json(output / "local-predictions.jsonl", row)
        jobs = branch_jobs(test_states, dev_states)
        # Direct fixed-model baselines cover all held-out tasks. Failed tasks
        # already have identical fresh prompts in the matched bank; reuse those
        # observed draws without charging the producer prefix to direct policies.
        failed_ids = {c["task_id"] for c in test_states}
        for task in split["evaluation_task_ids"]:
            if task in failed_ids:
                continue
            for model in config["target_models"]:
                for draw in range(config["branch_repeats"]):
                    jobs.append({"task_id": task, "split": "evaluation", "action": "direct", "arm": "fresh", "model_name": model,
                                 "draw": draw, "messages": recovery_messages(problems[task], "fresh")})
        batch(jobs)
    except (BudgetStopped, BackendStopped, ValueError) as exc:
        status = type(exc).__name__ + ": " + str(exc)
    except KeyboardInterrupt:
        status = "interrupted; in-flight reservations retained"
    except Exception as exc:
        status = "infrastructure_error: " + type(exc).__name__
        raise
    finally:
        result = {"status": status, "requests": client.ledger.calls, "collection_cost_usd": float(client.ledger.spent),
            "unresolved_reserved_usd": float(sum(client.ledger.pending.values())), "budget_usd": float(client.ledger.limit),
            "initial_attempts": len(initial), "failed_checkpoints": len(checkpoints), "branch_and_direct_draws": len(branches),
            "api_forecasts": len(predictions), "prior_committed_usd": config["prior_committed_usd"]}
        (output / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    """Plan without model calls by default; live execution uses the remaining approved ceiling."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--key-stdin", action="store_true")
    parser.add_argument("--import-run", help="Explicit stopped-run import into a fresh output/journal; never automatic")
    parser.add_argument("--reconciliation", help="Account-level zero-charge reconciliation for insured source errors")
    parser.add_argument("--continue-evaluation-from", help="Explicit frozen-development phase transition; all unknown reserves stay held")
    args = parser.parse_args()
    if args.import_run and args.continue_evaluation_from:
        parser.error("Select one explicit continuation mode")
    config = json.loads(Path(args.config).read_text())
    problems, split = load_experiment(config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    ids = split["development_task_ids"] + split["evaluation_task_ids"]
    manifest = {"config": config, "config_sha256": digest(config), "split": split,
        "created_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "prompt_sha256": {t: digest(problems[t]["prompt"]) for t in ids}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if not args.live:
        print(json.dumps({"status": "plan_only", "development_tasks": len(split["development_task_ids"]),
                          "evaluation_tasks": len(split["evaluation_task_ids"]), "reserved_tasks": len(split["reserved_task_ids"])}))
        return 0
    if args.budget_usd is None or Decimal(str(args.budget_usd)) > Decimal(str(config["run_ceiling_usd"])):
        parser.error("Declare a budget at or below the frozen remaining run ceiling")
    if Decimal(str(args.budget_usd)) + Decimal(str(config["prior_committed_usd"])) > Decimal(str(config["campaign_ceiling_usd"])):
        parser.error("Cumulative campaign ceiling would be exceeded")
    key = sys.stdin.readline().strip() if args.key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        parser.error("Supply key through stdin or environment")
    ledger = BudgetLedger(output / "budget.jsonl", args.budget_usd)
    imported = []
    development = None
    if args.continue_evaluation_from:
        development = continue_frozen_development(Path(args.continue_evaluation_from), output, ledger, config)
        manifest["continuation_provenance"] = development["provenance"]
    if args.import_run:
        imported, provenance = import_completed(Path(args.import_run), output, ledger, config,
            Path(args.reconciliation) if args.reconciliation else None)
        manifest["import_provenance"] = provenance
    verifier = SandboxVerifier()
    manifest["sandbox"] = verifier.preflight()
    if args.import_run or args.continue_evaluation_from:
        manifest["reference_preflight_reused_with_identical_evaluator"] = True
    else:
        for t in ids:
            p = problems[t]
            for mode in ("base_feedback", "heldout"):
                if not verifier.check(p, p["prompt"] + p["canonical_solution"], mode)["passed"]:
                    raise RuntimeError("Reference failed " + mode + ": " + t)
    client = (ImportedClient(key, config, output, ledger, imported, records(Path(args.import_run), "evaluations"))
              if args.import_run else OpenRouterClient(key, config, output, ledger))
    manifest["preflight"] = client.preflight()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    result = run(config, problems, split, client, verifier, output, development)
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
