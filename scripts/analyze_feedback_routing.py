"""Audit and analyze fixed feedback-only trajectories without making model calls."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np

from vao.decisions.feedback_routing import POLICIES, messages, model_for, reservation


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def audit(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    assert hashlib.sha256((root / "config.json").read_bytes()).hexdigest() == manifest["config_sha256"]
    base = Path(config["bundle"])
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[1] / base
    task_path = base / config["task_file"]
    assert hashlib.sha256(task_path.read_bytes()).hexdigest() == config["task_sha256"]
    tasks = {t["task_id"]: t for t in json.loads(task_path.read_text())}
    assert len(tasks) == config["tasks"]
    calls = records(root / "calls.jsonl")
    scored = records(root / "evaluations.jsonl")
    outcomes = records(root / "outcomes.jsonl")
    transport = records(root / "transport.jsonl")
    by_call = {r["call"]: r for r in calls}
    by_score = {r["call"]: r for r in scored}
    assert len(by_call) == len(calls) and len(by_score) == len(scored)
    assert set(by_score) <= set(by_call)
    holds = {}; settled = {}; known = Decimal(0)
    for event in records(root / "budget.jsonl"):
        call = event["call"]
        if event["event"] == "reserve":
            assert call not in holds and call not in settled
            holds[call] = Decimal(str(event["reserved_usd"]))
        else:
            assert event["event"] == "settle" and call in holds
            cost = Decimal(str(event["cost_usd"]))
            assert 0 <= cost <= holds.pop(call)
            settled[call] = cost
            known += cost
        assert known + sum(holds.values()) <= Decimal(str(config["run_ceiling_usd"]))
    assert set(by_call) == set(settled)
    assert {r["call"] for r in transport} <= set(holds)
    for call in calls:
        assert call["task_id"] in tasks and call["replicate"] in range(config["replicates"])
        assert call["model"] == config["models"][call["model_name"]]["id"]
        assert call["provider"].lower() == "siliconflow"
        assert Decimal(str(call["usage"]["cost"])) == settled[call["call"]]
        if call["call"] in by_score:
            score = by_score[call["call"]]
            assert score["task_id"] == call["task_id"]
            assert score["cost_usd"] == float(settled[call["call"]])
            assert hashlib.sha256(score["solution"].encode()).hexdigest() == score["solution_sha256"]
            if score["solution"]:
                assert score["solution"] == json.loads(call["content"])["solution"]
            assert (score["heldout"] is not None) == score["visible"]["passed"]
    keys = [(r["task_id"], r["replicate"], r["policy"]) for r in outcomes]
    assert len(set(keys)) == len(keys)
    for row in outcomes:
        assert row["policy"] in POLICIES and row["task_id"] in tasks
        assert row["replicate"] in range(config["replicates"])
        assert 1 <= len(row["calls"]) <= config["maximum_attempts"]
        cost = Decimal(0)
        previous = None
        for attempt, call_id in enumerate(row["calls"]):
            call, score = by_call[call_id], by_score[call_id]
            assert call["task_id"] == row["task_id"] and call["replicate"] == row["replicate"]
            assert call["attempt"] == attempt
            assert call["policy"] == ("small_feedback" if attempt == 0 and row["policy"] != "large_direct" else row["policy"])
            model = model_for(row["policy"], attempt)
            assert call["model_name"] == model
            assert call["messages"] == messages(tasks[row["task_id"]], previous["visible"] if previous else None)
            assert previous is None or not previous["visible"]["passed"]
            assert cost + reservation(config, model) <= Decimal(str(config["task_budget_usd"]))
            cost += settled[call_id]
            previous = score
        assert abs(row["cost_usd"] - float(cost)) < 1e-12
        passed = bool(previous["visible"]["passed"] and previous["heldout"]["passed"])
        assert row["passed"] == passed
        assert row["public_false_positive"] == bool(previous["visible"]["passed"] and not passed)
        if row["stop_reason"] == "public_pass":
            assert previous["visible"]["passed"]
        elif row["stop_reason"] == "task_budget":
            assert cost + reservation(config, model_for(row["policy"], len(row["calls"]))) > Decimal(str(config["task_budget_usd"]))
        elif row["stop_reason"] == "maximum_attempts":
            assert len(row["calls"]) == config["maximum_attempts"]
        else:
            assert row["stop_reason"] == "task_or_campaign_admission"
    complete = len(outcomes) == len(tasks) * config["replicates"] * len(POLICIES)
    if complete:
        assert not holds and set(by_call) == set(by_score)
        assert {c for row in outcomes for c in row["calls"]} == set(by_call)
    return {"config": config, "tasks": tasks, "calls": calls, "evaluations": scored, "outcomes": outcomes,
            "integrity": {"complete": complete, "known_usd": float(known), "held_usd": float(sum(holds.values())),
                          "run_upper_usd": float(known + sum(holds.values())), "observed_calls": len(calls),
                          "unscored_responses": len(set(by_call) - set(by_score)), "pending_admissions": sorted(holds)}}


def analyze(data: dict) -> dict:
    config, tasks, outcomes = data["config"], data["tasks"], data["outcomes"]
    indexed = {(r["task_id"], r["replicate"], r["policy"]): r for r in outcomes}
    ids = sorted(tasks)
    reps = config["replicates"]
    n = len(ids)
    rates = {}; arrays = {}
    for policy in POLICIES:
        values = np.array([[float(indexed[(t, r, policy)]["passed"]) if (t, r, policy) in indexed else np.nan
                            for r in range(reps)] for t in ids])
        arrays[policy] = values
        rows = [r for r in outcomes if r["policy"] == policy]
        known_success = sum(r["passed"] for r in rows)
        missing = n * reps - len(rows)
        rates[policy] = {"observed": len(rows), "expected": n * reps, "successes": known_success,
                         "all_selected_success_bounds": [known_success / (n * reps), (known_success + missing) / (n * reps)],
                         "mean_observed_cost_usd": float(np.mean([r["cost_usd"] for r in rows])) if rows else None,
                         "mean_observed_verifier_seconds": float(np.mean([r["verifier_seconds"] for r in rows])) if rows else None,
                         "public_false_positives": sum(r["public_false_positive"] for r in rows),
                         "stop_reasons": dict(Counter(r["stop_reason"] for r in rows))}
    pairs = [("immediate_large_feedback", "small_feedback", .05),
             ("delayed_large_feedback", "small_feedback", .05 / 3),
             ("large_direct", "small_feedback", .05 / 3),
             ("immediate_large_feedback", "large_direct", .05 / 3)]
    contrasts = []
    for left, right, alpha in pairs:
        a, b = arrays[left], arrays[right]
        complete = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
        diff = (a[complete] - b[complete]).mean(axis=1)
        rng = np.random.default_rng(config["seed"])
        if len(diff):
            draws = diff[rng.integers(0, len(diff), (10000, len(diff)))].mean(axis=1)
            interval = [float(x) for x in np.quantile(draws, [alpha / 2, 1 - alpha / 2])]
            estimate = float(diff.mean())
        else:
            interval, estimate = None, None
        low = np.nan_to_num(a, nan=0) - np.nan_to_num(b, nan=1)
        high = np.nan_to_num(a, nan=1) - np.nan_to_num(b, nan=0)
        contrasts.append({"left": left, "right": right, "alpha": alpha, "complete_task_clusters": int(sum(complete)),
                          "estimate": estimate, "interval": interval,
                          "all_selected_missing_bounds": [float(low.mean()), float(high.mean())]})
    primary = contrasts[0]
    gate = bool(data["integrity"]["complete"] and primary["interval"] and primary["interval"][0] > 0 and primary["estimate"] >= .05)
    by_call = {r["call"]: r for r in data["calls"]}
    by_score = {r["call"]: r for r in data["evaluations"]}
    failed_prefixes = {(r["task_id"], r["replicate"]) for r in data["calls"] if r["policy"] == "small_feedback"
                       and r["attempt"] == 0 and r["call"] in by_score and not by_score[r["call"]]["visible"]["passed"]}
    for policy in POLICIES:
        rows = [r for r in outcomes if r["policy"] == policy]
        selected = [r for r in rows if (r["task_id"], r["replicate"]) in failed_prefixes]
        rates[policy]["conditional_on_initial_small_public_failure"] = {
            "observed": len(selected), "successes": sum(r["passed"] for r in selected)}
        rates[policy]["mean_observed_api_seconds"] = float(np.mean([
            sum(by_call[c]["elapsed_seconds"] for c in row["calls"]) for row in rows])) if rows else None
    return {"status": "complete_prespecified_bank" if data["integrity"]["complete"] else "incomplete_descriptive_bank",
            "integrity": data["integrity"], "task_clusters": n, "replicates": reps, "policies": rates,
            "contrasts": contrasts, "primary_gate_passed": gate,
            "selector": "Not trained. A positive stage-1 gate is necessary, not sufficient, for a later held-out selector claim.",
            "cost_scope": "Equal API-dollar admission cap; actual spend, local verifier time, and latency are not equalized."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--integrity-only", action="store_true")
    args = parser.parse_args()
    data = audit(args.input)
    if not args.integrity_only:
        if not (args.input / "summary.json").exists():
            raise RuntimeError("No treatment analysis while collection is active")
        result = analyze(data)
    else:
        result = data["integrity"]
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(data["integrity"], indent=2))


if __name__ == "__main__":
    main()
