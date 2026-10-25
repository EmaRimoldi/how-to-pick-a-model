"""Collect matched one-checkpoint HumanEval+ continuations through OpenRouter."""

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
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .verification import SandboxVerifier, visible_examples


ACTIONS = ("continue", "restart", "switch_fresh", "switch_context")
STRATEGIES = ("cheap_stop", "strong_direct", *ACTIONS)
SYSTEM = (
    'Solve the Python task using only the standard library. Return one JSON object '
    'with a "solution" string containing the complete Python source, including '
    'imports and the requested function. Do not include tests, markdown, or explanations.'
)


def digest(value: object) -> str:
    """Hash a serializable artifact for checkpoint and provenance references."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_tasks(config: dict) -> tuple[list[dict], str]:
    """Select development tasks from public prompts before observing model outcomes."""
    from evalplus.data import get_human_eval_plus, get_human_eval_plus_hash

    if importlib.metadata.version("evalplus") != "0.3.1":
        raise ValueError("Install the locked continuation-pilot extra (EvalPlus 0.3.1)")
    tasks = get_human_eval_plus()
    dataset_hash = get_human_eval_plus_hash()
    if dataset_hash != config["dataset_hash"]:
        raise ValueError("Dataset changed; revise the frozen pilot configuration")
    eligible = sorted((p for p in tasks.values() if visible_examples(p["prompt"]) > 0),
                      key=lambda p: int(p["task_id"].split("/")[1]))
    random.Random(config["seed"]).shuffle(eligible)
    if not 1 <= config["task_count"] <= len(eligible):
        raise ValueError("Invalid task_count")
    return eligible[:config["task_count"]], dataset_hash


def messages_for(problem: dict, action: str, checkpoint: dict | None = None) -> list[dict]:
    """Build prompts from public information; hidden scores are never an argument."""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": problem["prompt"]}]
    if action in {"continue", "switch_context"}:
        if checkpoint is None:
            raise ValueError("A continuation requires an observable checkpoint")
        messages += [{"role": "assistant", "content": checkpoint["content"]},
                     {"role": "user", "content": "Revise the previous solution using only this "
                      "feedback from the public examples:\n" + json.dumps(checkpoint["feedback"], sort_keys=True)}]
    elif action not in {"initial", "restart", "switch_fresh", "strong_direct"}:
        raise ValueError("Unknown action")
    return messages


def evaluate_response(problem: dict, call: dict, verifier: SandboxVerifier) -> dict:
    """Persist visible feedback separately from evaluation-only full-suite scores."""
    try:
        if call.get("finish_reason", "stop") != "stop":
            raise ValueError("Completion did not terminate normally")
        solution = json.loads(call["content"])["solution"]
        if not isinstance(solution, str) or not solution.strip():
            raise ValueError("Empty solution")
    except (ValueError, KeyError, TypeError):
        return {"solution": "", "solution_sha256": digest(""),
                "visible": {"passed": False, "status": "format_error",
                            "feedback": 'Return valid JSON with a nonempty "solution" string'},
                "heldout": {"passed": False, "status": "format_error"},
                "verifier_seconds": 0.0}
    start = time.perf_counter()
    visible = verifier.check(problem, solution, "visible")
    heldout = verifier.check(problem, solution, "heldout")
    return {"solution": solution, "solution_sha256": digest(solution),
            "visible": visible, "heldout": heldout,
            "verifier_seconds": time.perf_counter() - start}


def summarize(rows: list[dict], config: dict) -> dict:
    """Compare only complete matched tasks; report repeated draws as dependent samples."""
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["strategy"]][row["task_id"]].append(row)
    expected = {s: config["branch_repeats"] for s in STRATEGIES}
    expected["cheap_stop"] = 1
    expected["strong_direct"] = config["direct_repeats"]
    complete = None
    for strategy in STRATEGIES:
        ids = {task for task, values in grouped[strategy].items() if len(values) == expected[strategy]}
        complete = ids if complete is None else complete & ids
    complete = sorted(complete or [])
    strategies = {}
    for strategy in STRATEGIES:
        task_success = [mean(float(r["passed"]) for r in grouped[strategy][task]) for task in complete]
        task_cost = [mean(r["policy_cost_usd"] for r in grouped[strategy][task]) for task in complete]
        strategies[strategy] = {"tasks": len(complete),
            "success_rate": mean(task_success) if complete else None,
            "mean_policy_cost_usd": mean(task_cost) if complete else None}
    return {"complete_task_ids": complete, "strategies": strategies,
            "evaluation_split": "development-pilot-only",
            "claim": "Exploratory one-checkpoint calibration; no learned-controller or generalization claim"}


def write_report(output: Path, rows: list[dict], config: dict, ledger: BudgetLedger, status: str) -> dict:
    """Write a reproducible, cost-aware summary without treating branches as free runs."""
    summary = summarize(rows, config)
    summary.update(status=status, actual_collection_cost_usd=float(ledger.spent),
                   unresolved_reserved_usd=float(sum(ledger.pending.values())),
                   budget_usd=float(ledger.limit), requests=ledger.calls)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    lines = ["# OpenRouter continuation pilot", "", summary["claim"], "",
             f"Status: `{status}`. Complete matched tasks: {len(summary['complete_task_ids'])}.",
             f"Collection cost: ${ledger.spent:.6f}; unresolved reservations: "
             f"${sum(ledger.pending.values()):.6f}; budget ceiling: ${ledger.limit}.", "",
             "| Strategy | Tasks | Full HumanEval+ success | Mean policy cost (USD) |",
             "| --- | --- | --- | --- |"]
    for strategy, values in summary["strategies"].items():
        rate = "n/a" if values["success_rate"] is None else f"{values['success_rate']:.1%}"
        cost = "n/a" if values["mean_policy_cost_usd"] is None else f"{values['mean_policy_cost_usd']:.6f}"
        lines.append(f"| {strategy} | {values['tasks']} | {rate} | {cost} |")
    lines += ["", "Policy cost includes the initial small-model attempt plus the chosen action. "
              "Collection cost includes every sampled counterfactual branch. Branch repeats from "
              "one checkpoint are not independent tasks. Visible-example success stops a policy; "
              "the final base/plus scores never trigger retries or appear in model feedback.", "",
              "This development pilot is excluded from any future held-out evaluation. "
              "Passing public examples is not proof of full-suite correctness. This is not a "
              "trained controller, a pure parameter-scaling study, or a state-of-the-art result.", ""]
    (output / "report.md").write_text("\n".join(lines))
    return summary


def collect(config: dict, problems: list[dict], client: OpenRouterClient,
            verifier: SandboxVerifier, output: Path) -> dict:
    """Run serial, price-bounded calls and matched fresh/context actions."""
    rows = []
    status = "complete"

    def outcome(problem, strategy, draw, call, scored, prefix=None, reused=False):
        """Store a policy outcome with its deployment cost, including its prefix."""
        cost = call["cost_usd"] + (prefix["cost_usd"] if prefix else 0)
        row = {"task_id": problem["task_id"], "strategy": strategy, "draw": draw,
               "call": call["call"], "parent_call": prefix["call"] if prefix else None,
               "reused_prefix": reused, "passed": scored["heldout"]["passed"],
               "visible_passed": scored["visible"]["passed"], "policy_cost_usd": cost,
               "solution_sha256": scored["solution_sha256"]}
        append_json(output / "outcomes.jsonl", row)
        rows.append(row)

    def sample(problem, model, action, draw, checkpoint=None, parent=None):
        """Generate one independent draw and evaluate it outside model feedback."""
        seed = config["seed"] + int(problem["task_id"].split("/")[1]) * 1000
        offsets = {"initial": 0, "strong_direct": 10, "continue": 20,
                   "restart": 30, "switch_fresh": 40, "switch_context": 50}
        call = client.complete(model, messages_for(problem, action, checkpoint), seed + offsets[action] + draw,
            {"task_id": problem["task_id"], "action": action, "draw": draw,
             "parent_call": parent["call"] if parent else None})
        scored = evaluate_response(problem, call, verifier)
        append_json(output / "evaluations.jsonl", {"call": call["call"],
            "task_id": problem["task_id"], **scored})
        return call, scored

    try:
        for index, problem in enumerate(problems):
            prefix, initial = sample(problem, "small", "initial", 0)
            outcome(problem, "cheap_stop", 0, prefix, initial)
            checkpoint = {"content": prefix["content"], "feedback": initial["visible"]}
            # Interleave direct controls and arms in a frozen random order to
            # reduce time-of-run confounding. Repeats reuse this exact checkpoint.
            jobs = [("strong_direct", d) for d in range(config["direct_repeats"])]
            jobs += [(a, d) for a in ACTIONS for d in range(config["branch_repeats"])]
            random.Random(config["seed"] + index).shuffle(jobs)
            for action, draw in jobs:
                if action in ACTIONS and initial["visible"]["passed"]:
                    outcome(problem, action, draw, prefix, initial, reused=True)
                    continue
                model = "small" if action in {"continue", "restart"} else "large"
                call, scored = sample(problem, model, action, draw, checkpoint,
                                      prefix if action in ACTIONS else None)
                outcome(problem, action, draw, call, scored,
                        prefix if action in ACTIONS else None)
            print(json.dumps({"tasks_completed": index + 1, "tasks_total": len(problems),
                              "calls": client.ledger.calls,
                              "spent_usd": float(client.ledger.spent)}), flush=True)
    except (BudgetStopped, BackendStopped) as exc:
        status = type(exc).__name__ + ": " + str(exc)
    except KeyboardInterrupt:
        status = "interrupted; unresolved reservations retained"
    except Exception as exc:
        status = "infrastructure_error: " + type(exc).__name__
        raise
    finally:
        summary = write_report(output, rows, config, client.ledger, status)
    return summary


def main() -> int:
    """Plan by default; paid execution requires --live and an explicit <=$2 budget."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget-usd", type=float)
    parser.add_argument("--key-stdin", action="store_true", help="Read one key from stdin instead of the environment")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    problems, dataset_hash = load_tasks(config)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        git_sha = None
    manifest = {"config": config, "config_sha256": digest(config), "dataset_hash": dataset_hash,
        "task_ids": [p["task_id"] for p in problems], "split": "development-pilot-only",
        "created_utc": datetime.now(timezone.utc).isoformat(), "git_sha": git_sha,
        "python": platform.python_version(), "platform": platform.system(),
        "task_prompt_hashes": {p["task_id"]: digest(p["prompt"]) for p in problems}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if not args.live:
        print(json.dumps({"status": "plan_only", "task_ids": manifest["task_ids"],
                          "maximum_requests": len(problems) * (1 + config["direct_repeats"]
                                                              + 4 * config["branch_repeats"])}))
        return 0
    if args.budget_usd is None:
        parser.error("--live requires --budget-usd")
    key = sys.stdin.readline().strip() if args.key_stdin else os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        parser.error("Provide OPENROUTER_API_KEY or --key-stdin")
    ledger = BudgetLedger(output / "budget.jsonl", args.budget_usd)
    verifier = SandboxVerifier()
    manifest["sandbox"] = verifier.preflight()
    # Catch task/example/verifier incompatibilities before spending API credit.
    for problem in problems:
        ref = problem["prompt"] + problem["canonical_solution"]
        if not verifier.check(problem, ref, "visible")["passed"]:
            raise RuntimeError("Reference fails public doctests: " + problem["task_id"])
        if not verifier.check(problem, ref, "heldout")["passed"]:
            raise RuntimeError("Reference fails EvalPlus: " + problem["task_id"])
    client = OpenRouterClient(key, config, output, ledger)
    manifest["preflight"] = client.preflight()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "preflight_passed", "budget_usd": args.budget_usd}), flush=True)
    summary = collect(config, problems, client, verifier, output)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
