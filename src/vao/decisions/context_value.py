"""Prospective forecasts and matched artifact/feedback ablations after visible failure."""

from __future__ import annotations

import argparse
import ast
import json
import os
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import SYSTEM, digest, evaluate_response, load_tasks, messages_for
from .verification import SandboxVerifier


ARMS = ("fresh", "artifact", "feedback", "artifact_feedback")
VIEWS = ("task_only", "state")


def select_tasks(config: dict) -> tuple[list[dict], list[str], str]:
    """Freeze a new public-prompt task pool, leaving an untouched reserve."""
    all_tasks, dataset_hash = load_tasks({**config, "task_count": config["eligible_task_count"]})
    excluded = set(config["excluded_task_ids"])
    eligible = [p for p in all_tasks if p["task_id"] not in excluded]
    if not 1 <= config["task_count"] < len(eligible):
        raise ValueError("Keep at least one task untouched for subsequent validation")
    return eligible[:config["task_count"]], [p["task_id"] for p in eligible[config["task_count"]:]], dataset_hash


def observable_features(solution: str, feedback: dict) -> dict:
    """Extract cheap observable features without running code or consulting hidden scores."""
    try:
        tree = ast.parse(solution)
        syntax_valid = True
        nodes = len(list(ast.walk(tree)))
    except SyntaxError:
        syntax_valid, nodes = False, 0
    text = feedback.get("feedback", "")
    return {"source_characters": len(solution), "source_lines": len(solution.splitlines()),
            "syntax_valid": syntax_valid, "ast_nodes": nodes,
            "visible_status": feedback["status"],
            "visible_attempted": feedback.get("attempted"), "visible_failed": feedback.get("failed"),
            "name_error": "NameError" in text, "syntax_error": "SyntaxError" in text,
            "type_error": "TypeError" in text, "timeout": feedback["status"] == "timeout"}


def branch_messages(problem: dict, arm: str, checkpoint: dict) -> list[dict]:
    """Use the same instruction/template, varying only inclusion of public state fields."""
    if arm not in ARMS:
        raise ValueError("Unknown context arm")
    payload = {"task": problem["prompt"],
               "previous_solution": checkpoint["solution"] if arm in {"artifact", "artifact_feedback"} else None,
               "public_example_feedback": checkpoint["feedback"] if arm in {"feedback", "artifact_feedback"} else None}
    instruction = ("Solve this task. When a previous solution or public-example feedback is supplied, "
                   "you may use it, revise it, or discard it. Return a complete solution.\n")
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": instruction + json.dumps(payload, sort_keys=True)}]


def forecast_messages(problem: dict, view: str, checkpoint: dict, config: dict) -> list[dict]:
    """Forecast before branch generation; both views know a previous attempt visibly failed."""
    if view not in VIEWS:
        raise ValueError("Unknown forecast view")
    keys = [model + "." + arm for model in config["target_models"] for arm in ARMS]
    instruction = (
        "Predict the probability that ONE next Python solution passes a broader correctness "
        "test suite, not merely its public examples. A previous attempt by "
        + config["models"]["small"]["id"] + " failed public examples. "
        "The next solver is sampled at temperature " + str(config["temperature"]) + ". "
        "fresh receives the task only; artifact also receives the previous code; feedback "
        "also receives its public-example feedback; artifact_feedback receives both. "
        "The same instruction allows the solver to revise or discard supplied work. "
        "No broader-test outcomes are available. Return only JSON of the form "
        '{"probabilities": {"MODEL.ARM": 0.5, ...}}, with every requested key and numbers in [0,1]. '
        "Do not solve the task or give explanations. Requested keys: " + json.dumps(keys)
    )
    payload = {"task": problem["prompt"],
               "models": {m: config["models"][m]["id"] for m in config["target_models"]}}
    if view == "state":
        payload.update(previous_solution=checkpoint["solution"],
                       public_example_feedback=checkpoint["feedback"], features=checkpoint["features"])
    return [{"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(payload, sort_keys=True)}]


def parse_forecast(call: dict, config: dict) -> tuple[dict, bool]:
    """Keep malformed forecasts in evaluation with a declared 0.5 operational fallback."""
    keys = [m + "." + a for m in config["target_models"] for a in ARMS]
    try:
        if call.get("finish_reason") != "stop":
            raise ValueError("Incomplete forecast")
        values = json.loads(call["content"])["probabilities"]
        if set(values) != set(keys) or not all(type(p) in {int, float} and 0 <= p <= 1 for p in values.values()):
            raise ValueError("Invalid probabilities")
        return values, True
    except (ValueError, KeyError, TypeError, AttributeError):
        return {key: 0.5 for key in keys}, False


def collect_context(config: dict, problems: list[dict], client: OpenRouterClient,
                    verifier: SandboxVerifier, output: Path) -> dict:
    """Collect every prefix, then forecasts before randomized matched branch outcomes."""
    checkpoints = []
    branches = []
    predictions = []
    status = "complete"
    initial_count = 0

    def score(problem, call):
        scored = evaluate_response(problem, call, verifier)
        append_json(output / "evaluations.jsonl", {"call": call["call"], "task_id": problem["task_id"], **scored})
        return scored

    try:
        for index, problem in enumerate(problems):
            for draw in range(config["prefix_repeats"]):
                call = client.complete("small", messages_for(problem, "initial"), config["seed"] + index * 100 + draw,
                                       {"task_id": problem["task_id"], "action": "initial", "draw": draw})
                scored = score(problem, call)
                initial_count += 1
                if not scored["visible"]["passed"]:
                    checkpoint = {"checkpoint_id": str(call["call"]), "parent_call": call["call"],
                        "task_id": problem["task_id"], "prefix_draw": draw, "prefix_cost_usd": call["cost_usd"],
                        "solution": scored["solution"], "solution_sha256": scored["solution_sha256"],
                        "feedback": scored["visible"], "features": observable_features(scored["solution"], scored["visible"])}
                    append_json(output / "checkpoints.jsonl", checkpoint)
                    checkpoints.append(checkpoint)
            print(json.dumps({"phase": "prefixes", "tasks_completed": index + 1,
                "failed_checkpoints": len(checkpoints), "spent_usd": float(client.ledger.spent)}), flush=True)

        by_task = {p["task_id"]: p for p in problems}
        for index, checkpoint in enumerate(checkpoints):
            problem = by_task[checkpoint["task_id"]]
            metadata = {"task_id": problem["task_id"], "checkpoint_id": checkpoint["checkpoint_id"],
                        "parent_call": checkpoint["parent_call"]}
            views = list(VIEWS)
            random.Random(config["seed"] + index).shuffle(views)
            for view in views:
                call = client.complete("small", forecast_messages(problem, view, checkpoint, config), config["seed"],
                    {**metadata, "action": "forecast", "view": view})
                probabilities, valid = parse_forecast(call, config)
                record = {**metadata, "call": call["call"], "view": view, "valid": valid,
                          "probabilities": probabilities, "cost_usd": call["cost_usd"]}
                append_json(output / "predictions.jsonl", record)
                predictions.append(record)
            jobs = [(m, a, d) for m in config["target_models"] for a in ARMS for d in range(config["branch_repeats"])]
            random.Random(config["seed"] + 10000 + index).shuffle(jobs)
            for model, arm, draw in jobs:
                call = client.complete(model, branch_messages(problem, arm, checkpoint), config["seed"] + draw,
                    {**metadata, "action": arm, "model_name": model, "draw": draw})
                scored = score(problem, call)
                record = {**metadata, "call": call["call"], "model_name": model, "arm": arm,
                          "draw": draw, "passed": scored["heldout"]["passed"],
                          "visible_passed": scored["visible"]["passed"], "incremental_cost_usd": call["cost_usd"],
                          "prefix_and_action_cost_usd": checkpoint["prefix_cost_usd"] + call["cost_usd"]}
                append_json(output / "branches.jsonl", record)
                branches.append(record)
            print(json.dumps({"phase": "branches", "checkpoints_completed": index + 1,
                              "checkpoints_total": len(checkpoints), "spent_usd": float(client.ledger.spent)}), flush=True)
    except (BudgetStopped, BackendStopped) as exc:
        status = type(exc).__name__ + ": " + str(exc)
    except KeyboardInterrupt:
        status = "interrupted; pending reservations retained"
    except Exception as exc:
        status = "infrastructure_error: " + type(exc).__name__
        raise
    finally:
        summary = {"status": status, "initial_checkpoints": initial_count,
                   "visible_failed_checkpoints": len(checkpoints), "branches": len(branches),
                   "forecasts": len(predictions), "collection_cost_usd": float(client.ledger.spent),
                   "unresolved_reserved_usd": float(sum(client.ledger.pending.values())),
                   "budget_usd": float(client.ledger.limit), "requests": client.ledger.calls}
        (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> int:
    """Plan by default; explicitly authorized live collection is bounded by at most $2."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--key-stdin", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    problems, reserved, dataset_hash = select_tasks(config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"config": config, "config_sha256": digest(config), "dataset_hash": dataset_hash,
        "task_ids": [p["task_id"] for p in problems], "reserved_task_ids": reserved,
        "task_prompt_hashes": {p["task_id"]: digest(p["prompt"]) for p in problems},
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": platform.python_version(), "platform": platform.system(),
        "scope": "prospective zero-shot forecast diagnostic; no trained controller"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if not args.live:
        print(json.dumps({"status": "plan_only", "tasks": len(problems), "reserved_tasks": len(reserved),
            "maximum_requests": len(problems) * config["prefix_repeats"] *
            (1 + len(VIEWS) + len(config["target_models"]) * len(ARMS) * config["branch_repeats"])}))
        return 0
    if args.budget_usd is None:
        parser.error("--live requires --budget-usd")
    key = sys.stdin.readline().strip() if args.key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        parser.error("Supply OPENROUTER_API_KEY or --key-stdin")
    ledger = BudgetLedger(output / "budget.jsonl", args.budget_usd)
    verifier = SandboxVerifier()
    manifest["sandbox"] = verifier.preflight()
    for problem in problems:
        reference = problem["prompt"] + problem["canonical_solution"]
        for mode in ("visible", "heldout"):
            if not verifier.check(problem, reference, mode)["passed"]:
                raise RuntimeError("Reference fails " + mode + ": " + problem["task_id"])
    client = OpenRouterClient(key, config, output, ledger)
    manifest["preflight"] = client.preflight()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    result = collect_context(config, problems, client, verifier, output)
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
