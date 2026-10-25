"""Audit prospective context-value records and compare matched outcomes by task cluster."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import mean

import numpy as np

from vao.decisions.context_value import (ARMS, VIEWS, branch_messages,
    forecast_messages, observable_features, parse_forecast)
from vao.decisions.pilot import digest


def read_rows(root: Path, name: str) -> list[dict]:
    """Absent optional streams mean no recorded observations, never fabricated outcomes."""
    path = root / (name + ".jsonl")
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def require(condition: bool, message: str) -> None:
    """Keep audit validation enabled even under Python's optimized mode."""
    if not condition:
        raise ValueError(message)


def estimate_by_task(values: dict[str, list[float]]) -> dict:
    """Weight tasks equally; suppress bootstrap intervals for fewer than five clusters."""
    task_means = np.array([mean(values[key]) for key in sorted(values)])
    interval = None
    if len(task_means) >= 5:
        rng = np.random.default_rng(20261023)
        bootstrap = rng.choice(task_means, size=(4000, len(task_means)), replace=True).mean(axis=1)
        interval = [float(v) for v in np.quantile(bootstrap, [0.025, 0.975])]
    return {"mean": float(task_means.mean()) if len(task_means) else None,
            "task_clusters": len(task_means), "task_cluster_bootstrap_95": interval}


def paired_analysis(checkpoints: list[dict], branches: list[dict], predictions: list[dict], config: dict) -> dict:
    """Score only complete matched checkpoints; repeats never inflate task sample size."""
    grouped = defaultdict(lambda: defaultdict(list))
    forecasts = defaultdict(dict)
    cp_by_id = {c["checkpoint_id"]: c for c in checkpoints}
    require(len(cp_by_id) == len(checkpoints), "Duplicate checkpoint")
    seen = set()
    for row in branches:
        identity = (row["checkpoint_id"], row["model_name"], row["arm"], row["draw"])
        require(identity not in seen, "Duplicate matched branch")
        seen.add(identity)
        require(row["checkpoint_id"] in cp_by_id, "Unknown parent checkpoint")
        require(row["task_id"] == cp_by_id[row["checkpoint_id"]]["task_id"], "Branch task mismatch")
        require(row["model_name"] in config["target_models"] and row["arm"] in ARMS
                and row["draw"] in range(config["branch_repeats"]), "Invalid branch cell")
        grouped[row["checkpoint_id"]][row["model_name"] + "." + row["arm"]].append(row)
    for record in predictions:
        cp, view = record["checkpoint_id"], record["view"]
        require(cp in cp_by_id and view in VIEWS and view not in forecasts[cp], "Duplicate or unknown forecast")
        forecasts[cp][view] = record
    keys = [m + "." + a for m in config["target_models"] for a in ARMS]
    complete = [cp for cp in cp_by_id if set(grouped[cp]) == set(keys)
                and all(len(grouped[cp][key]) == config["branch_repeats"] for key in keys)
                and set(forecasts[cp]) == set(VIEWS)]
    cells = {key: defaultdict(list) for key in keys}
    costs = {key: defaultdict(list) for key in keys}
    contrasts = {m + "." + contrast: defaultdict(list) for m in config["target_models"]
                 for contrast in ("artifact_minus_fresh", "feedback_minus_fresh", "both_minus_fresh", "interaction")}
    brier = {view: defaultdict(list) for view in (*VIEWS, "constant_0.5")}
    forecast_cost = {view: defaultdict(list) for view in VIEWS}
    brier_difference = defaultdict(list)
    checkpoints_detail = []
    invalid = Counter()
    for cp in complete:
        task = cp_by_id[cp]["task_id"]
        outcomes = {key: mean(float(r["passed"]) for r in grouped[cp][key]) for key in keys}
        for key in keys:
            cells[key][task].append(outcomes[key])
            costs[key][task].append(mean(r["incremental_cost_usd"] for r in grouped[cp][key]))
        for model in config["target_models"]:
            fresh, artifact, feedback, both = (outcomes[model + "." + a] for a in ARMS)
            for name, value in (("artifact_minus_fresh", artifact - fresh),
                                ("feedback_minus_fresh", feedback - fresh),
                                ("both_minus_fresh", both - fresh),
                                ("interaction", both - artifact - feedback + fresh)):
                contrasts[model + "." + name][task].append(value)
        scores = {}
        for view in VIEWS:
            forecast = forecasts[cp][view]
            invalid[view] += not forecast["valid"]
            scores[view] = mean((forecast["probabilities"][key] - float(row["passed"])) ** 2
                                for key in keys for row in grouped[cp][key])
            brier[view][task].append(scores[view])
            forecast_cost[view][task].append(forecast["cost_usd"])
        brier["constant_0.5"][task].append(0.25)
        brier_difference[task].append(scores["state"] - scores["task_only"])
        checkpoints_detail.append({"checkpoint_id": cp, "task_id": task, "success_rates": outcomes,
            "brier": scores, "features": cp_by_id[cp]["features"],
            "predicted_both_minus_fresh": {view: {m: forecasts[cp][view]["probabilities"][m + ".artifact_feedback"]
                - forecasts[cp][view]["probabilities"][m + ".fresh"] for m in config["target_models"]} for view in VIEWS}})
    return {"complete_checkpoint_ids": complete, "incomplete_checkpoint_ids": sorted(set(cp_by_id) - set(complete)),
            "complete_failed_task_ids": sorted({cp_by_id[cp]["task_id"] for cp in complete}),
            "cells": {key: {"success": estimate_by_task(cells[key]), "incremental_api_usd": estimate_by_task(costs[key])} for key in keys},
            "contrasts": {key: estimate_by_task(values) for key, values in contrasts.items()},
            "forecast_brier": {view: estimate_by_task(values) for view, values in brier.items()},
            "forecast_api_usd": {view: estimate_by_task(values) for view, values in forecast_cost.items()},
            "state_minus_task_brier": estimate_by_task(brier_difference),
            "invalid_forecasts_in_paired_sample": dict(invalid), "checkpoints": checkpoints_detail}


def audit(root: Path) -> dict:
    """Reconcile billing, parent identity, visible-state prompts and prospective forecast order."""
    manifest = json.loads((root / "manifest.json").read_text())
    config = manifest["config"]
    require(digest(config) == manifest["config_sha256"], "Configuration digest changed")
    require(not set(manifest["task_ids"]) & set(config["excluded_task_ids"]), "Prior-pilot task leakage")
    require(not set(manifest["task_ids"]) & set(config["quality_exclusions"]), "Excluded task leakage")
    require(not set(manifest["task_ids"]) & set(manifest["reserved_task_ids"]), "Reserve task leakage")
    calls = read_rows(root, "calls")
    budget = read_rows(root, "budget")
    evaluations = read_rows(root, "evaluations")
    checkpoints = read_rows(root, "checkpoints")
    branches = read_rows(root, "branches")
    predictions = read_rows(root, "predictions")
    summary = json.loads((root / "summary.json").read_text())
    by_call = {c["call"]: c for c in calls}
    by_eval = {e["call"]: e for e in evaluations}
    require(len(by_call) == len(calls) and len(by_eval) == len(evaluations), "Duplicate call/evaluation")
    reserves = {r["call"]: Decimal(str(r["reserved_usd"])) for r in budget if r["event"] == "reserve"}
    settled = {r["call"]: Decimal(str(r["cost_usd"])) for r in budget if r["event"] == "settle"}
    require(len(reserves) == sum(r["event"] == "reserve" for r in budget), "Duplicate reservation")
    require(len(settled) == sum(r["event"] == "settle" for r in budget), "Duplicate settlement")
    require(set(settled) == set(by_call) and set(settled) <= set(reserves), "Receipt/settlement coverage mismatch")
    require(set(by_eval) == {c["call"] for c in calls if c["action"] != "forecast"}, "Evaluation coverage mismatch")
    require({p["call"] for p in predictions} == {c["call"] for c in calls if c["action"] == "forecast"}, "Forecast coverage mismatch")
    require({b["call"] for b in branches} == {c["call"] for c in calls if c["action"] in ARMS}, "Branch coverage mismatch")
    for call in calls:
        charge = Decimal(str(call["usage"]["cost"]))
        require(charge.is_finite() and 0 <= charge == settled[call["call"]] <= reserves[call["call"]], "Receipt charge mismatch")
        require(call["provider"] == "SiliconFlow" and call["seed_sent"] is None, "Provider/sampler changed")
        require(call["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) == 0, "Reasoning returned")
        require(call["usage"]["prompt_tokens"] <= config["input_token_ceiling"]
                and call["usage"]["completion_tokens"] <= config["max_tokens"], "Token ceiling exceeded")
        require(call["task_id"] in manifest["task_ids"], "Unknown task in receipts")
    paid, pending = sum(settled.values()), sum(reserves[k] for k in set(reserves) - set(settled))
    require(paid == Decimal(str(summary["collection_cost_usd"])) and pending == Decimal(str(summary["unresolved_reserved_usd"])), "Summary billing mismatch")
    require(paid + pending <= Decimal(str(summary["budget_usd"])), "Budget exceeded")
    initial = [c for c in calls if c["action"] == "initial"]
    prefix_ids = {(c["task_id"], c["draw"]) for c in initial}
    require(len(prefix_ids) == len(initial), "Duplicate initial attempt")
    require(all(c["model"] == config["models"]["small"]["id"] for c in initial), "Prefix model changed")
    if summary["status"] == "complete":
        expected = {(task, draw) for task in manifest["task_ids"] for draw in range(config["prefix_repeats"])}
        require(prefix_ids == expected, "Completed run lacks initial task/draw coverage")
    failed = {c["call"] for c in initial if not by_eval[c["call"]]["visible"]["passed"]}
    require({c["parent_call"] for c in checkpoints} == failed, "Checkpoint selection differs from visible failures")
    require(len(initial) == summary["initial_checkpoints"] and len(branches) == summary["branches"]
            and len(predictions) == summary["forecasts"], "Summary count mismatch")
    cp_by_id = {cp["checkpoint_id"]: cp for cp in checkpoints}
    for cp in checkpoints:
        parent = by_call[cp["parent_call"]]
        scored = by_eval[parent["call"]]
        require(cp["task_id"] == parent["task_id"] and cp["solution"] == scored["solution"]
                and cp["solution_sha256"] == digest(cp["solution"]), "Parent artifact mismatch")
        require(cp["feedback"] == scored["visible"] and cp["features"] == observable_features(cp["solution"], cp["feedback"]), "Observable projection changed")
        require(Decimal(str(cp["prefix_cost_usd"])) == settled[parent["call"]], "Prefix cost mismatch")
    for record in predictions + branches:
        cp = cp_by_id[record["checkpoint_id"]]
        call = by_call[record["call"]]
        parent = by_call[cp["parent_call"]]
        require(record["parent_call"] == cp["parent_call"] == call["parent_call"]
                and cp["task_id"] == call["task_id"] == record["task_id"], "Parent identity changed")
        problem = {"prompt": parent["messages"][1]["content"]}
        if call["action"] == "forecast":
            require(call["model"] == config["models"]["small"]["id"], "Forecaster model changed")
            require(call["messages"] == forecast_messages(problem, record["view"], cp, config), "Forecast prompt changed")
            probs, valid = parse_forecast(call, config)
            require(probs == record["probabilities"] and valid == record["valid"], "Forecast parse changed")
            require(Decimal(str(record["cost_usd"])) == settled[call["call"]], "Forecast cost mismatch")
        else:
            require(call["action"] == record["arm"] and call["model_name"] == record["model_name"]
                    and call["model"] == config["models"][record["model_name"]]["id"], "Branch model/arm mismatch")
            require(call["messages"] == branch_messages(problem, record["arm"], cp), "Branch prompt changed")
            require(record["passed"] == by_eval[call["call"]]["heldout"]["passed"]
                    and record["visible_passed"] == by_eval[call["call"]]["visible"]["passed"], "Branch score mismatch")
            require(Decimal(str(record["incremental_cost_usd"])) == settled[call["call"]], "Branch cost mismatch")
            preds = [p for p in predictions if p["checkpoint_id"] == record["checkpoint_id"]]
            require(len(preds) == 2 and all(parent["call"] < p["call"] < record["call"] for p in preds), "Forecasts were not prospective")
    analysis = paired_analysis(checkpoints, branches, predictions, config)
    if summary["status"] == "complete":
        require(not analysis["incomplete_checkpoint_ids"], "Completed run lacks matched branches")
    false_positives = [c for c in initial if by_eval[c["call"]]["visible"]["passed"] and not by_eval[c["call"]]["heldout"]["passed"]]
    return {"billing_and_prospective_order_verified": True, "collection": summary,
            "collector_git_sha": manifest.get("git_sha"),
            "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "initial_full_suite_passes": sum(by_eval[c["call"]]["heldout"]["passed"] for c in initial),
            "initial_visible_false_positive_count": len(false_positives),
            "initial_visible_false_positive_tasks": sorted({c["task_id"] for c in false_positives}),
            "failed_checkpoint_tasks": sorted({c["task_id"] for c in checkpoints}),
            "model_calls": len(calls), "calls_by_action": dict(Counter(c["action"] for c in calls)),
            "forecast_api_cost_usd": float(sum(settled[c["call"]] for c in calls if c["action"] == "forecast")),
            "candidate_verifier_seconds": sum(e["verifier_seconds"] for e in evaluations),
            "model_request_seconds": sum(c["elapsed_seconds"] for c in calls), "analysis": analysis}


def report_markdown(report: dict) -> str:
    """State empirical boundaries alongside paired effects and forecast scores."""
    analysis = report["analysis"]
    counts = report["collection"]
    lines = ["# Context-value prospective diagnostic", "",
        f"Status: `{counts['status']}`. {counts['initial_checkpoints']} initial attempts; "
        f"{counts['visible_failed_checkpoints']} visible failures; "
        f"{len(analysis['complete_checkpoint_ids'])} complete matched checkpoints across "
        f"{len(analysis['complete_failed_task_ids'])} tasks.", "",
        f"API collection cost: ${counts['collection_cost_usd']:.6f}; "
        f"unresolved conservative reservations: ${counts['unresolved_reserved_usd']:.6f}. "
        f"Forecast API cost included: ${report['forecast_api_cost_usd']:.6f}.", "",
        "| Model.condition | Task-macro full-suite success | Mean incremental API USD |",
        "| --- | --- | --- |"]
    for key, cell in analysis["cells"].items():
        success, cost = cell["success"]["mean"], cell["incremental_api_usd"]["mean"]
        lines.append(f"| {key} | {success:.1%} | {cost:.8f} |" if success is not None else f"| {key} | n/a | n/a |")
    lines += ["", "| Paired contrast | Task-macro success difference | Task-cluster bootstrap 95% interval |",
              "| --- | --- | --- |"]
    for key, value in analysis["contrasts"].items():
        interval = value["task_cluster_bootstrap_95"]
        interval_text = f"[{interval[0]:+.1%}, {interval[1]:+.1%}]" if interval else "insufficient task clusters"
        delta = f"{value['mean']:+.1%}" if value["mean"] is not None else "n/a"
        lines.append(f"| {key} | {delta} | {interval_text} |")
    lines += ["", "| Prospective forecast | Brier score (lower is better) |", "| --- | --- |"]
    for view, value in analysis["forecast_brier"].items():
        score = f"{value['mean']:.5f}" if value["mean"] is not None else "n/a"
        lines.append(f"| {view} | {score} |")
    lines += ["", f"Invalid forecasts retained with 0.5 fallback: {analysis['invalid_forecasts_in_paired_sample']}.",
        f"Incomplete matched checkpoints excluded from paired effects: {analysis['incomplete_checkpoint_ids']}.", "",
        "Repeated draws are averaged within checkpoints, then checkpoints within tasks; tasks are equally weighted. "
        "Intervals resample tasks (4000 draws, seed 20261023), are exploratory and are not adjusted for multiple contrasts. "
        "They cover variation in this selected task subset, not provider drift or benchmark contamination.", "",
        "Forecasts were saved before the branch outcomes. These are zero-shot forecasts, not a trained controller. "
        "A forecast deployment must pay its own forecasting cost; fixed-arm costs in the table exclude forecasting "
        "and the already-sunk prefix. The receipt bundle accounts for every paid call.", "",
        "Artifact/feedback inclusion also changes prompt length. Feedback can quote code. No length-matched "
        "irrelevant-context control or equal-dollar adaptive-policy comparison is present. Public feedback may "
        "miss failures detected by the broader evaluation suite. No novelty, policy-superiority or general-gain claim.", ""]
    lines += ["## Forecast overhead", ""]
    for view, value in analysis["forecast_api_usd"].items():
        if value["mean"] is not None:
            lines.append(f"Mean {view} forecast API cost per failed checkpoint (task macro): ${value['mean']:.8f}.")
    lines += ["", "A better forecast is economically useful only when the resulting decisions recover "
              "its overhead. This analysis does not equate lower Brier score with net cost savings.", ""]
    return "\n".join(lines)


def plot(report: dict, output: Path) -> None:
    """Plot measured task-macro effects and prospective forecast errors."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    analysis = report["analysis"]
    if not analysis["complete_checkpoint_ids"]:
        return
    models = list(dict.fromkeys(key.split(".")[0] for key in analysis["cells"]))
    fig, axes = plt.subplots(1, len(models) + 1, figsize=(12, 4.4), layout="constrained")
    for ax, model in zip(axes, models):
        values = [100 * analysis["cells"][model + "." + a]["success"]["mean"] for a in ARMS]
        bars = ax.bar(range(4), values, color=["#a3adb5", "#467ba3", "#75a798", "#cf8853"])
        ax.set_xticks(range(4), ["Fresh", "Code", "Feedback", "Both"], rotation=25, ha="right")
        ax.set_ylim(0, 115)
        ax.set_title(("9B" if model == "small" else "27B") + " next-attempt success (%)")
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
    brier = analysis["forecast_brier"]
    bars = axes[-1].bar(range(3), [brier[k]["mean"] for k in ("task_only", "state", "constant_0.5")],
                         color=["#467ba3", "#cf8853", "#a3adb5"])
    axes[-1].set_xticks(range(3), ["Task only", "State", "0.5 fallback"], rotation=25, ha="right")
    axes[-1].set_title("Prospective Brier score (lower better)")
    axes[-1].bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    axes[-1].set_ylim(0, max(0.3, max(brier[k]["mean"] for k in brier) * 1.2))
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Context-value diagnostic: {len(analysis['complete_checkpoint_ids'])} failed checkpoints, "
                 f"{len(analysis['complete_failed_task_ids'])} task clusters\nTask-macro means; no learned controller or held-out policy gain", fontsize=11)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    """Read only saved data; write a fresh analysis directory without provider calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(Path(args.input))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "report.md").write_text(report_markdown(report))
    plot(report, output / "context_value.png")
    print(json.dumps({"calls": report["model_calls"], "cost_usd": report["collection"]["collection_cost_usd"],
                      "matched_checkpoints": len(report["analysis"]["complete_checkpoint_ids"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
