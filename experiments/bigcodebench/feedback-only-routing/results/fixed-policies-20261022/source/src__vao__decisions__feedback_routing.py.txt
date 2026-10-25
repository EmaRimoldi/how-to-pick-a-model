"""Prospective fixed-policy comparison with feedback only, before any selector."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import time

from .bigcode import BigCodeVerifier, sha
from .openrouter import BackendStopped, BudgetLedger, BudgetStopped, OpenRouterClient, append_json
from .pilot import SYSTEM


POLICIES = ("small_feedback", "immediate_large_feedback", "delayed_large_feedback", "large_direct")


def reservation(config: dict, model: str) -> Decimal:
    m = config["models"][model]
    return (Decimal(config["input_token_ceiling"]) * Decimal(str(m["input_per_million"]))
            + Decimal(config["max_tokens"]) * Decimal(str(m["output_per_million"]))) / 1_000_000


def model_for(policy: str, attempt: int) -> str:
    """Attempt zero is the initial solution, not a recovery attempt."""
    if policy not in POLICIES or attempt < 0:
        raise ValueError("Unknown policy/attempt")
    if policy == "large_direct" or (policy == "immediate_large_feedback" and attempt > 0):
        return "large"
    if policy == "delayed_large_feedback" and attempt >= 2:
        return "large"
    return "small"


def messages(task: dict, visible: dict | None) -> list[dict]:
    payload = {"task": task["complete_prompt"]}
    if visible is not None:
        payload["public_test_feedback"] = {k: visible[k] for k in ("status", "attempted", "failed") if k in visible}
        payload["public_test_feedback"]["details"] = str(visible.get("feedback", ""))[:1200]
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content":
        "Return a complete Python solution including required imports. Use the public test feedback, "
        "if supplied, to produce a new solution.\n" + json.dumps(payload, sort_keys=True)}]


def evaluate(task: dict, call: dict, verifier: BigCodeVerifier) -> dict:
    start = time.perf_counter()
    try:
        source = json.loads(call["content"])["solution"]
        if call["finish_reason"] != "stop" or not isinstance(source, str) or not source.strip():
            raise ValueError("Incomplete solution")
    except (ValueError, KeyError, TypeError):
        source = ""
        visible = {"passed": False, "status": "format_error", "feedback": "Return JSON with a complete solution string"}
    else:
        visible = verifier.check(task, source, "visible")
    # Hidden tests are evaluation only, and never influence another request.
    hidden = verifier.check(task, source, "heldout") if visible["passed"] else None
    return {"call": call["call"], "task_id": task["task_id"], "solution": source,
            "solution_sha256": hashlib.sha256(source.encode()).hexdigest(), "visible": visible,
            "heldout": hidden, "cost_usd": call["cost_usd"], "verifier_seconds": time.perf_counter() - start}


def trajectory(config: dict, task: dict, policy: str, client, verifier, output: Path,
               prefix: dict | None = None) -> dict:
    """A real feedback-updating trajectory; no synthetic handoff replay."""
    attempts = [prefix] if prefix is not None else []
    cost = Decimal(str(prefix["cost_usd"])) if prefix else Decimal(0)
    reason = "maximum_attempts"
    cap = Decimal(str(config["task_budget_usd"]))
    while len(attempts) < config["maximum_attempts"]:
        if attempts and attempts[-1]["visible"]["passed"]:
            reason = "public_pass"
            break
        model = model_for(policy, len(attempts))
        if cost + reservation(config, model) > cap:
            reason = "task_budget"
            break
        visible = attempts[-1]["visible"] if attempts else None
        # Campaign exhaustion is missing research data, not a policy failure.
        # The per-policy ceiling was checked above, before admission.
        call = client.complete(model, messages(task, visible), config["seed"], {
            "task_id": task["task_id"], "replicate": task.get("replicate", 0),
            "policy": policy, "attempt": len(attempts), "model_name": model})
        result = evaluate(task, call, verifier)
        append_json(output / "evaluations.jsonl", result)
        attempts.append(result)
        cost += Decimal(str(call["cost_usd"]))
    if attempts and attempts[-1]["visible"]["passed"]:
        reason = "public_pass"
    terminal = attempts[-1] if attempts else None
    passed = bool(terminal and terminal["visible"]["passed"] and terminal["heldout"]["passed"])
    return {"task_id": task["task_id"], "replicate": task.get("replicate", 0),
            "policy": policy, "calls": [a["call"] for a in attempts],
            "cost_usd": float(cost), "passed": passed, "stop_reason": reason,
            "public_false_positive": bool(terminal and terminal["visible"]["passed"] and not passed),
            "verifier_seconds": sum(a["verifier_seconds"] for a in attempts),
            "terminal": terminal}


def collect(config: dict, tasks: list[dict], client, verifier, output: Path) -> dict:
    outcomes = []
    def task_run(task):
        # A shared initial 9B response is counted in every applicable policy's
        # deployment cost and paid once in collection accounting.
        prefix_row = trajectory(dict(config, maximum_attempts=1), task, "small_feedback", client, verifier, output)
        prefix = prefix_row["terminal"]
        if prefix is None:
            raise BudgetStopped("Initial request was not admitted")
        order = list(POLICIES)
        random.Random(config["seed"] + int(task["task_id"].split("/")[-1]) + 10000 * task.get("replicate", 0)).shuffle(order)
        for policy in order:
            row = trajectory(config, task, policy, client, verifier, output,
                             None if policy == "large_direct" else prefix)
            row.pop("terminal")
            append_json(output / "outcomes.jsonl", row)
            outcomes.append(row)
    error = None
    jobs = [dict(task, replicate=replicate) for task in tasks for replicate in range(config["replicates"])]
    random.Random(config["seed"]).shuffle(jobs)
    with ThreadPoolExecutor(max_workers=config["workers"]) as pool:
        pending = [pool.submit(task_run, task) for task in jobs]
        for future in as_completed(pending):
            try:
                future.result()
            except Exception as exc:
                # Stop siblings before any further admission, preserving all holds.
                client.ledger.stopped = True
                if error is None or isinstance(exc, BackendStopped):
                    error = exc
    return {"status": "complete" if error is None and len(outcomes) == len(jobs) * len(POLICIES) else "incomplete",
            "tasks": len(tasks), "observed_policy_outcomes": len(outcomes),
            "replicates": config["replicates"],
            "stop_error": type(error).__name__ if error else None,
            "known_cost_usd": float(client.ledger.spent),
            "unresolved_reservations_usd": float(sum(client.ledger.pending.values())),
            "collection_cap_usd": config["run_ceiling_usd"]}


def load_frozen(config_path: Path) -> tuple[dict, list[dict]]:
    config = json.loads(config_path.read_text())
    root = config_path.parent.parent
    tasks_path = root / config["task_file"]
    if sha(tasks_path) != config["task_sha256"]:
        raise ValueError("Frozen tasks changed")
    if sha(root / "data/reference-audit.json") != config["reference_audit_sha256"]:
        raise ValueError("Frozen reference qualification changed")
    for name, expected in config["source_hashes"].items():
        if sha(Path(name)) != expected:
            raise ValueError("Frozen source changed: " + name)
    tasks = json.loads(tasks_path.read_text())
    if len({t["task_id"] for t in tasks}) != len(tasks) or len(tasks) != config["tasks"]:
        raise ValueError("Frozen task identity/count mismatch")
    return config, tasks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config, tasks = load_frozen(args.config)
    if not args.execute:
        print(json.dumps({"mode": "plan_only", "tasks": len(tasks), "policies": POLICIES,
            "task_budget_usd": config["task_budget_usd"], "run_cap_usd": config["run_ceiling_usd"]}, indent=2))
        return
    if not args.output:
        parser.error("--execute requires a fresh --output")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise RuntimeError("Commit reviewed protocol/source before live collection")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "config.json").write_bytes(args.config.read_bytes())
    manifest = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "config_sha256": sha(args.config), "started_utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version, "resume": "forbidden; no admitted request may be reissued"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    ledger = BudgetLedger(args.output / "budget.jsonl", config["run_ceiling_usd"], maximum_limit_usd=5)
    # Read from an un-echoed pipe: never an argument, environment variable, or file.
    key = sys.stdin.readline().strip()
    if not key.startswith("sk-or-"):
        raise ValueError("An OpenRouter key must be supplied through standard input")
    client = OpenRouterClient(key, config, args.output, ledger)
    verifier = BigCodeVerifier(timeout=15)
    preflight = {"sandbox": verifier.preflight(), "provider": client.preflight()}
    (args.output / "preflight.json").write_text(json.dumps(preflight, indent=2) + "\n")
    summary = collect(config, tasks, client, verifier, args.output)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
