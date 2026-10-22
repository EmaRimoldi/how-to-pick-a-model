"""Audit frozen held-out recovery data and replay its finite budgeted policy bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import mean

import numpy as np

from vao.decisions.context_value import ARMS, parse_forecast
from vao.decisions.pilot import SYSTEM, digest
from vao.decisions.recovery import CONDITIONS, forecast_messages, producer_messages, recovery_messages
from vao.decisions.recovery_import import job_key
from vao.decisions.recovery_policy import fit_policy, predict


def read(root: Path, name: str) -> list[dict]:
    """Read a saved stream without running candidates or contacting a provider."""
    path = root / (name + ".jsonl")
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reservation(config: dict, model: str) -> Decimal:
    """Use the same advance worst-case admission rule as the live collector."""
    prices = config["models"][model]
    return (Decimal(config["input_token_ceiling"]) * Decimal(str(prices["input_per_million"]))
            + Decimal(config["max_tokens"]) * Decimal(str(prices["output_per_million"]))) / 1_000_000


def paired_interval(values: list[float]) -> dict:
    """Resample independent held-out tasks, including failures and abstentions."""
    if not values:
        return {"mean": None, "task_clusters": 0, "bootstrap_95": None}
    a = np.array(values)
    interval = None
    if len(a) >= 5:
        rng = np.random.default_rng(20261024)
        samples = rng.choice(a, size=(4000, len(a)), replace=True).mean(axis=1)
        interval = np.quantile(samples, [0.025, 0.975]).tolist()
    return {"mean": float(a.mean()), "task_clusters": len(a), "bootstrap_95": interval}


def audit(root: Path) -> dict:
    """Reject broken billing, split leakage, altered prompts and nonprospective forecasts."""
    manifest = json.loads((root / "manifest.json").read_text())
    config, split = manifest["config"], manifest["split"]
    summary = json.loads((root / "summary.json").read_text())
    require(summary["status"] == "complete", "Only a complete frozen evaluation supports this report")
    require(digest(config) == manifest["config_sha256"], "Configuration changed")
    sets = [set(split[k]) for k in ("development_task_ids", "evaluation_task_ids", "reserved_task_ids", "reference_exclusions")]
    require(not any(sets[i] & sets[j] for i in range(4) for j in range(i)), "Task split overlap")
    calls, ledger = read(root, "calls"), read(root, "budget")
    initial, checkpoints, branches = read(root, "initial"), read(root, "checkpoints"), read(root, "branches")
    evaluations, forecasts = read(root, "evaluations"), read(root, "predictions")
    local, phases = read(root, "local-predictions"), read(root, "phases")
    policy = json.loads((root / "frozen-policy.json").read_text())
    by_call = {r["call"]: r for r in calls}
    by_eval = {r["call"]: r for r in evaluations}
    by_cp = {r["checkpoint_id"]: r for r in checkpoints}
    require(len(by_call) == len(calls) and len(by_eval) == len(evaluations), "Duplicate receipt/evaluation")
    require(len(by_cp) == len(checkpoints), "Duplicate parent checkpoint")
    reserves = {r["call"]: Decimal(str(r["reserved_usd"])) for r in ledger if r["event"] == "reserve"}
    settled = {r["call"]: Decimal(str(r["cost_usd"])) for r in ledger if r["event"] == "settle"}
    require(len(reserves) == sum(r["event"] == "reserve" for r in ledger)
            and len(settled) == sum(r["event"] == "settle" for r in ledger), "Duplicate ledger event")
    censor_path = root / "transport-censoring.json"
    censor = json.loads(censor_path.read_text()) if censor_path.exists() else None
    missing = set(censor["censored_request_ids"]) if censor else set()
    require(set(by_call) == set(settled) and set(reserves) == set(settled) | missing
            and not missing & set(settled), "Unresolved or missing billed request")
    held = sum((reserves[i] for i in missing), Decimal(0))
    require(summary["requests"] == len(calls) + len(missing), "Request count changed")
    if censor:
        require(held == Decimal(str(censor["censored_reserved_usd"])) and len(missing) <= config["workers"] + 2, "Censored reservation changed")
        require(digest(calls[:censor["source_responses"]]) == censor["source_calls_sha256"]
                and digest(ledger[:censor["source_budget_events"]]) == censor["source_budget_sha256"], "Stopped source journal changed")
        require(censor["frozen_policy_sha256"] == digest(policy), "Policy changed after transport stop")
    for call in calls:
        model = config["models"][call["model_name"]]
        charge = Decimal(str(call["usage"]["cost"]))
        require(charge.is_finite() and 0 <= charge == settled[call["call"]] <= reserves[call["call"]], "Charge mismatch")
        require(reserves[call["call"]] == reservation(config, call["model_name"]), "Admission ceiling changed")
        require(call["provider"] == model.get("provider_name", "SiliconFlow") and call["model"] == model["id"], "Model/provider changed")
        require(call["seed_sent"] is None and not (call["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens", 0), "Sampler/reasoning changed")
        if call.get("billing_source") == "published_zero_completion_insurance":
            require(call["finish_reason"] == "error" and charge == 0 and not call["content"], "Invalid insured zero")
        else:
            require(call["usage"]["prompt_tokens"] <= config["input_token_ceiling"]
                    and call["usage"]["completion_tokens"] <= config["max_tokens"], "Token ceiling exceeded")
    paid = sum(settled.values())
    require(paid == Decimal(str(summary["collection_cost_usd"])) and held == Decimal(str(summary["unresolved_reserved_usd"])), "Summary billing mismatch")
    require(paid + held <= Decimal(str(summary["budget_usd"])) <= Decimal(str(config["run_ceiling_usd"])), "Run ceiling exceeded")
    require(paid + held + Decimal(str(config["prior_committed_usd"])) <= Decimal(str(config["campaign_ceiling_usd"])), "Campaign ceiling exceeded")
    if (root / "import-provenance.json").exists():
        provenance = json.loads((root / "import-provenance.json").read_text())
        uses = read(root, "import-uses")
        imported_ids = set(range(1, provenance["imported_calls"] + 1))
        require(len(uses) == len(imported_ids) and {u["call"] for u in uses} == imported_ids, "Imported observations not reused exactly once")
        require(sum(settled[i] for i in imported_ids) == Decimal(str(provenance["imported_cost_usd"])), "Imported charge changed")
        for use in uses:
            call = by_call[use["call"]]
            require(use["job_sha256"] == job_key(call["model_name"], call["messages"], call), "Imported job identity changed")
    require(set(by_eval) == {c["call"] for c in calls if c["action"] != "forecast"}, "Evaluation coverage changed")
    require({r["call"] for r in initial} == {c["call"] for c in calls if c["action"] == "initial"}, "Initial receipt coverage changed")
    require({r["call"] for r in branches} == {c["call"] for c in calls if c["action"] in {"branch", "direct"}}, "Branch coverage changed")
    require({r["call"] for r in forecasts} == {c["call"] for c in calls if c["action"] == "forecast"}, "Forecast coverage changed")
    require(len({r["task_id"] for r in initial}) == len(initial) == len(sets[0] | sets[1]), "Missing/duplicate initial task")
    prompts = {}
    for row in initial:
        call = by_call[row["call"]]
        text = call["messages"][0]["content"]
        require(text.startswith(SYSTEM + "\n\n"), "Producer instruction changed")
        prompt = text[len(SYSTEM) + 2:]
        require(digest(prompt) == manifest["prompt_sha256"][row["task_id"]], "Prompt hash changed")
        prompts[row["task_id"]] = prompt
        require(call["messages"] == producer_messages({"prompt": prompt}), "Producer framing changed")
        label = "development" if row["task_id"] in sets[0] else "evaluation"
        producer = config.get("evaluation_producer", config["producer"]) if label == "evaluation" else config["producer"]
        require(row["split"] == call["split"] == label and call["model_name"] == producer, "Initial split/model changed")
        require(row["passed"] == by_eval[row["call"]]["heldout"]["passed"]
                and row["visible_passed"] == by_eval[row["call"]]["visible"]["passed"], "Initial score changed")
        require(Decimal(str(row["cost_usd"])) == settled[row["call"]], "Producer price changed")
    require({cp["parent_call"] for cp in checkpoints} == {r["call"] for r in initial if not r["visible_passed"]}, "Failure selection changed")
    for cp in checkpoints:
        scored = by_eval[cp["parent_call"]]
        require(cp["feedback"] == scored["visible"] and cp["solution"] == scored["solution"]
                and cp["solution_sha256"] == digest(cp["solution"]), "Observable checkpoint changed")
    phase = [p for p in phases if p["event"] == "policy_frozen"]
    require(len(phase) == 1 and phase[0]["policy_sha256"] == digest(policy), "Policy freeze changed")
    test_calls = [c for c in calls if c["split"] == "evaluation"]
    require(phase[0]["last_admitted_call"] < min(c["call"] for c in test_calls), "Evaluation began before policy freeze")
    require(set(policy["training_task_ids"]) == {c["task_id"] for c in checkpoints if c["split"] == "development"}, "Training task leakage")
    require(not set(policy["training_task_ids"]) & sets[1], "Held-out task in fitted model")
    require(digest([r for r in branches if r["split"] == "development"]) == policy["training_branches_sha256"], "Training data changed")
    refitted = fit_policy(sorted([c for c in checkpoints if c["split"] == "development"], key=lambda c: c["task_id"]),
        [r for r in branches if r["split"] == "development"], prompts, config)
    require(refitted["priors"] == policy["priors"] and refitted["best_fixed_action"] == policy["best_fixed_action"], "Fitted priors changed")
    # The saved JSON sorts keys; the live instruction lists the original
    # declared model/arm order. Reconstruct that order for exact prompt auditing.
    prompt_policy = {**policy, "priors": refitted["priors"]}
    for view in ("task", "state"):
        require(refitted["fits"][view]["features"] == policy["fits"][view]["features"], "Fitted feature order changed")
        for field in ("mean", "scale"):
            require(np.allclose(refitted["fits"][view][field], policy["fits"][view][field], atol=1e-12, rtol=1e-10), "Fitted feature normalization changed")
        for key, coefficients in refitted["fits"][view]["coefficients"].items():
            require(np.allclose(coefficients, policy["fits"][view]["coefficients"][key], atol=1e-12, rtol=1e-10), "Fitted weights differ from development data")
    seen = set()
    for row in branches:
        identity = (row["task_id"], row["model_name"], row["arm"], row["draw"])
        require(identity not in seen, "Duplicate recovery cell")
        seen.add(identity)
        call = by_call[row["call"]]
        require(all(row.get(k) == call.get(k) for k in ("task_id", "split", "action", "model_name", "arm", "draw",
                "checkpoint_id", "parent_call", "donor_checkpoint_id")), "Recovery receipt metadata changed")
        cp = by_cp.get(row["checkpoint_id"])
        donor = by_cp.get(row["donor_checkpoint_id"])
        if row["action"] == "branch":
            require(cp is not None and cp["task_id"] == row["task_id"] and cp["split"] == row["split"]
                    and cp["parent_call"] == row["parent_call"] == call["parent_call"], "Parent branch identity changed")
        if donor:
            require(donor["split"] == "development", "Held-out distractor donor")
        require(call["messages"] == recovery_messages({"prompt": prompts[row["task_id"]]}, row["arm"], cp, donor), "Recovery prompt changed")
        require(row["passed"] == by_eval[row["call"]]["heldout"]["passed"]
                and row["visible_passed"] == by_eval[row["call"]]["visible"]["passed"], "Recovery score changed")
        require(Decimal(str(row["incremental_cost_usd"])) == settled[row["call"]], "Recovery price changed")
    for cp in checkpoints:
        expected = {(cp["task_id"], m, a, d) for m in config["target_models"] for a in CONDITIONS for d in range(config["branch_repeats"])}
        require(expected <= seen, "Incomplete matched checkpoint")
    for task in sets[1]:
        expected = {(task, m, "fresh", d) for m in config["target_models"] for d in range(config["branch_repeats"])}
        require(expected <= seen, "Missing direct-model control")
    for row in forecasts:
        cp = by_cp[row["checkpoint_id"]]
        call = by_call[row["call"]]
        require(all(row[k] == call[k] for k in ("task_id", "split", "checkpoint_id", "parent_call", "view"))
                and call["model_name"] == "small", "Forecast receipt metadata changed")
        require(call["messages"] == forecast_messages({"prompt": prompts[row["task_id"]]}, row["view"], cp, prompt_policy, config), "Forecast prompt changed")
        probabilities, valid = parse_forecast(call, config)
        require(probabilities == row["probabilities"] and valid == row["valid"], "Forecast parse changed")
        require(Decimal(str(row["cost_usd"])) == settled[row["call"]], "Forecast fee changed")
        child_ids = [b["call"] for b in branches if b["checkpoint_id"] == cp["checkpoint_id"]]
        require(cp["parent_call"] < row["call"] < min(child_ids), "Forecast was not prospective")
    test_states = [cp for cp in checkpoints if cp["split"] == "evaluation"]
    require(len(forecasts) == 2 * len(test_states) and len(local) == len(test_states), "Forecast coverage incomplete")
    for row in local:
        cp = by_cp[row["checkpoint_id"]]
        require(row["policy_sha256"] == digest(policy), "Local model changed")
        require(row["probabilities"] == {v: predict(policy, prompts[row["task_id"]], cp, v) for v in ("global", "task", "state")}, "Local forecast changed")
        require(row["last_admitted_call"] < min(b["call"] for b in branches if b["checkpoint_id"] == cp["checkpoint_id"]), "Local forecast was not prospective")
    return {"config": config, "split": split, "summary": summary, "policy": policy, "calls": calls,
            "initial": initial, "checkpoints": checkpoints, "branches": branches, "forecasts": forecasts,
            "local": local, "evaluations": evaluations, "collector_git_sha": manifest["git_sha"]}


def rollout(task: str, policy_name: str, budget: float, data: dict, partition: str = "evaluation") -> dict:
    """Replay only observed draws; make admission decisions before looking at each bill."""
    cfg, fitted = data["config"], data["policy"]
    ceiling, spent = Decimal(str(budget)), Decimal(0)
    rows = [r for r in data["branches"] if r["task_id"] == task and r["split"] == partition]
    initial = next(r for r in data["initial"] if r["task_id"] == task)
    passed, attempts, reason, choice = False, 0, "budget", None
    def finish():
        return {"task_id": task, "policy": policy_name, "budget_usd": budget, "passed": passed,
                "cost_usd": float(spent), "net_utility_usd": cfg["solution_value_usd"] * passed - float(spent),
                "attempts_after_prefix": attempts, "termination": reason, "selected_action": choice}
    if policy_name.startswith("direct_"):
        choice = policy_name.removeprefix("direct_") + ".fresh"
    else:
        if reservation(cfg, cfg.get("evaluation_producer", cfg["producer"])) > ceiling:
            return finish()
        spent += Decimal(str(initial["cost_usd"]))
        if initial["visible_passed"]:
            passed, reason = initial["passed"], "public_pass"
            return finish()
        cp = next(c for c in data["checkpoints"] if c["task_id"] == task)
        probabilities = None
        if policy_name.startswith("fixed:"):
            choice = policy_name.removeprefix("fixed:")
        elif policy_name == "best_fixed":
            choice = fitted["best_fixed_action"]
        elif policy_name in {"global", "task", "state", "state_model_only", "state_context_small", "state_context_large"}:
            local = next(r for r in data["local"] if r["task_id"] == task)
            view = "state" if policy_name.startswith("state_") else policy_name
            probabilities = local["probabilities"][view]
            if policy_name == "state_model_only":
                probabilities = {k: v for k, v in probabilities.items() if k.endswith(".artifact_feedback")}
            elif policy_name.startswith("state_context_"):
                model = policy_name.removeprefix("state_context_")
                probabilities = {k: v for k, v in probabilities.items() if k.startswith(model + ".")}
        elif policy_name.startswith("api_"):
            if spent + reservation(cfg, "small") > ceiling:
                reason = "forecast_not_admitted"
                return finish()
            forecast = next(r for r in data["forecasts"] if r["task_id"] == task and r["view"] == policy_name.removeprefix("api_"))
            spent += Decimal(str(forecast["cost_usd"]))
            probabilities = forecast["probabilities"]
        else:
            raise ValueError("Unknown policy")
        if probabilities is not None:
            order = [m + "." + a for m in cfg.get("target_models", ["small", "large"]) for a in ARMS]
            admissible = [key for key in order if key in probabilities and spent + reservation(cfg, key.split(".")[0]) <= ceiling]
            if not admissible:
                return finish()
            choice = max(admissible, key=lambda key: cfg["solution_value_usd"] * probabilities[key] - fitted["mean_action_cost_usd"][key])
            if cfg["solution_value_usd"] * probabilities[choice] <= fitted["mean_action_cost_usd"][choice]:
                reason = "utility_abstention"
                return finish()
    model, arm = choice.split(".")
    candidates = sorted((r for r in rows if r["model_name"] == model and r["arm"] == arm), key=lambda r: r["draw"])
    require(len(candidates) == cfg["branch_repeats"], "Unobserved policy action")
    for row in candidates[:cfg["maximum_attempts"]]:
        if spent + reservation(cfg, model) > ceiling:
            reason = "budget"
            break
        spent += Decimal(str(row["incremental_cost_usd"]))
        attempts += 1
        if row["visible_passed"]:
            passed, reason = row["passed"], "public_pass"
            break
        reason = "attempt_cap"
    require(spent <= ceiling, "Replay overspent its declared budget")
    return finish()


def development_replay_best(data: dict, budget: float) -> str:
    """Select a stronger static comparator using development-only two-draw rollouts."""
    cfg = data["config"]
    keys = [m + "." + a for m in cfg["target_models"] for a in ARMS]
    scores = {key: mean(rollout(t, "fixed:" + key, budget, data, "development")["net_utility_usd"]
                        for t in data["split"]["development_task_ids"]) for key in keys}
    return max(keys, key=lambda key: scores[key])


def analyze(data: dict) -> tuple[dict, list[dict]]:
    """Compute declared primary utility comparison and explicitly secondary diagnostics."""
    cfg = data["config"]
    ids = sorted(data["split"]["evaluation_task_ids"])
    options = [m + "." + a for m in cfg["target_models"] for a in ARMS]
    policies = ["direct_small", "direct_large", "best_fixed", "global", "task", "state", "api_task_only", "api_state",
                "state_model_only", "state_context_small", "state_context_large"] + ["fixed:" + k for k in options]
    rollouts = [rollout(t, p, b, data) for b in cfg["task_budgets_usd"] for p in policies for t in ids]
    summary = {}
    replay_best = {}
    for b in cfg["task_budgets_usd"]:
        best_action = development_replay_best(data, b)
        replay_best[str(b)] = best_action
        for t in ids:
            row = rollout(t, "fixed:" + best_action, b, data)
            row["policy"] = "development_replay_best"
            rollouts.append(row)
        summary[str(b)] = {}
        for p in policies + ["development_replay_best"]:
            rows = [r for r in rollouts if r["budget_usd"] == b and r["policy"] == p]
            summary[str(b)][p] = {"tasks": len(rows), "success_rate": mean(r["passed"] for r in rows),
                "mean_api_cost_usd": mean(r["cost_usd"] for r in rows), "mean_net_utility_usd": mean(r["net_utility_usd"] for r in rows),
                "terminations": dict(Counter(r["termination"] for r in rows)),
                "selected_actions": dict(Counter(r["selected_action"] for r in rows if r["selected_action"] is not None))}
    baseline = {r["task_id"]: r for r in rollouts if r["budget_usd"] == 0.01 and r["policy"] == "best_fixed"}
    proposed = {r["task_id"]: r for r in rollouts if r["budget_usd"] == 0.01 and r["policy"] == "state"}
    stronger = {r["task_id"]: r for r in rollouts if r["budget_usd"] == 0.01 and r["policy"] == "development_replay_best"}
    primary = {"budget_usd": 0.01, "comparison": "state ridge minus development-selected best fixed recovery action",
        "net_utility_difference_usd": paired_interval([proposed[t]["net_utility_usd"] - baseline[t]["net_utility_usd"] for t in ids]),
        "success_difference": paired_interval([float(proposed[t]["passed"]) - float(baseline[t]["passed"]) for t in ids]),
        "api_cost_difference_usd": paired_interval([proposed[t]["cost_usd"] - baseline[t]["cost_usd"] for t in ids])}
    secondary_strong = paired_interval([proposed[t]["net_utility_usd"] - stronger[t]["net_utility_usd"] for t in ids])
    states = [cp for cp in data["checkpoints"] if cp["split"] == "evaluation"]
    recovery, token_stats, contrasts = {}, {}, {}
    for model in cfg["target_models"]:
        for arm in CONDITIONS:
            rows = [r for r in data["branches"] if r["split"] == "evaluation" and r["action"] == "branch" and r["model_name"] == model and r["arm"] == arm]
            per_task = [mean(float(r["passed"]) for r in rows if r["task_id"] == cp["task_id"]) for cp in states]
            recovery[model + "." + arm] = paired_interval(per_task)
            call_ids = {r["call"] for r in rows}
            tokens = [c["usage"]["prompt_tokens"] for c in data["calls"] if c["call"] in call_ids and c["usage"].get("prompt_tokens") is not None]
            token_stats[model + "." + arm] = {"mean": mean(tokens) if tokens else None, "min": min(tokens) if tokens else None, "max": max(tokens) if tokens else None}
        for name, positive, negative in (("both_minus_fresh", "artifact_feedback", "fresh"),
                                         ("code_minus_fresh", "artifact", "fresh"),
                                         ("feedback_minus_fresh", "feedback", "fresh"),
                                         ("both_minus_distractor", "artifact_feedback", "distractor")):
            differences = []
            for cp in states:
                rows = [r for r in data["branches"] if r["checkpoint_id"] == cp["checkpoint_id"] and r["model_name"] == model]
                differences.append(mean(float(r["passed"]) for r in rows if r["arm"] == positive)
                                   - mean(float(r["passed"]) for r in rows if r["arm"] == negative))
            contrasts[model + "." + name] = paired_interval(differences)
    brier, delta_error, failures = defaultdict(list), defaultdict(list), Counter()
    for cp in states:
        rows = [r for r in data["branches"] if r["checkpoint_id"] == cp["checkpoint_id"] and r["arm"] in ARMS]
        local = next(r for r in data["local"] if r["checkpoint_id"] == cp["checkpoint_id"])
        forecasts = {view: local["probabilities"][view] for view in ("global", "task", "state")}
        for record in data["forecasts"]:
            if record["checkpoint_id"] == cp["checkpoint_id"]:
                forecasts["api_" + record["view"]] = record["probabilities"]
                failures[record["view"]] += not record["valid"]
        actual = {key: mean(float(r["passed"]) for r in rows if r["model_name"] + "." + r["arm"] == key) for key in options}
        for view, probabilities in forecasts.items():
            brier[view].append(mean((probabilities[r["model_name"] + "." + r["arm"]] - float(r["passed"])) ** 2 for r in rows))
            delta_error[view].append(mean(((probabilities[m + "." + a] - probabilities[m + ".fresh"])
                - (actual[m + "." + a] - actual[m + ".fresh"])) ** 2 for m in cfg["target_models"] for a in ("artifact", "artifact_feedback")))
    initial_eval = [r for r in data["initial"] if r["split"] == "evaluation"]
    report = {"audit_passed": True, "collector_git_sha": data["collector_git_sha"],
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "collection": data["summary"], "development_tasks": len(data["split"]["development_task_ids"]),
        "producer_provider_transfer": cfg.get("evaluation_producer") is not None,
        "development_producer_endpoint": cfg["models"][cfg["producer"]].get("provider"),
        "evaluation_producer_endpoint": cfg["models"][cfg.get("evaluation_producer", cfg["producer"])].get("provider"),
        "evaluation_tasks": len(ids), "development_failed_tasks": len(data["policy"]["training_task_ids"]),
        "evaluation_failed_tasks": len(states), "evaluation_initial_full_passes": sum(r["passed"] for r in initial_eval),
        "evaluation_initial_false_positives": sum(r["visible_passed"] and not r["passed"] for r in initial_eval),
        "best_fixed_action_from_development": data["policy"]["best_fixed_action"],
        "development_replay_best_actions": replay_best,
        "secondary_state_minus_development_replay_best_utility_usd": secondary_strong,
        "primary": primary, "policies": summary, "conditional_recovery": recovery,
        "paired_context_contrasts": contrasts,
        "forecast_brier": {v: paired_interval(a) for v, a in brier.items()},
        "observed_benefit_mse": {v: paired_interval(a) for v, a in delta_error.items()},
        "invalid_api_forecasts": dict(failures), "prompt_token_controls": token_stats,
        "policy_backed_zero_charge_provider_errors": sum(c.get("billing_source") == "published_zero_completion_insurance" for c in data["calls"]),
        "provider_error_counts": dict(Counter(c["split"] + "." + c["model_name"] for c in data["calls"] if c["finish_reason"] == "error")),
        "public_pass_but_full_fail_draws": dict(Counter(r["model_name"] + "." + r["arm"] for r in data["branches"]
            if r["split"] == "evaluation" and r["visible_passed"] and not r["passed"])),
        "collection_verifier_seconds": sum(e["verifier_seconds"] for e in data["evaluations"]),
        "collection_request_seconds": sum(c["elapsed_seconds"] for c in data["calls"])}
    return report, rollouts


def markdown(report: dict) -> str:
    """Report the prespecified primary result before attractive secondary plots."""
    primary = report["primary"]["net_utility_difference_usd"]
    lines = ["# Held-out recovery validation", "",
        f"{report['development_tasks']} development tasks ({report['development_failed_tasks']} failed); "
        f"{report['evaluation_tasks']} untouched evaluation tasks ({report['evaluation_failed_tasks']} failed).", "",
        f"Development-selected fixed action: `{report['best_fixed_action_from_development']}`.", "",
        f"Primary state-ridge minus best-fixed net utility at $0.01/task: {primary['mean']:+.8f} USD; "
        f"task-bootstrap 95% interval {primary['bootstrap_95']}.", "",
        "| Policy at $0.01/task | Full verified success | Mean API USD | Mean net utility USD |",
        "| --- | --- | --- | --- |"]
    for key in ("direct_small", "direct_large", "best_fixed", "development_replay_best", "global", "task", "state", "api_task_only", "api_state",
                "state_model_only", "state_context_small", "state_context_large"):
        row = report["policies"]["0.01"][key]
        lines.append(f"| {key} | {row['success_rate']:.1%} | {row['mean_api_cost_usd']:.8f} | {row['mean_net_utility_usd']:.8f} |")
    lines += ["", "| Conditional recovery | Success | Task-bootstrap 95% interval |", "| --- | --- | --- |"]
    for key, row in report["conditional_recovery"].items():
        rate = f"{row['mean']:.1%}" if row["mean"] is not None else "n/a"
        lines.append(f"| {key} | {rate} | {row['bootstrap_95']} |")
    lines += ["", "| Paired context contrast | Success difference | Task-bootstrap 95% interval |", "| --- | --- | --- |"]
    for key, row in report["paired_context_contrasts"].items():
        delta = f"{row['mean']:+.1%}" if row["mean"] is not None else "n/a"
        lines.append(f"| {key} | {delta} | {row['bootstrap_95']} |")
    lines += ["", "| Predictor | Brier | Observed benefit MSE |", "| --- | --- | --- |"]
    for key, row in report["forecast_brier"].items():
        lines.append(f"| {key} | {row['mean']:.6f} | {report['observed_benefit_mse'][key]['mean']:.6f} |")
    total = report["collection"]["collection_cost_usd"]
    held = report["collection"]["unresolved_reserved_usd"]
    lines += ["", f"Collection: {report['collection']['requests']} model requests, ${total:.8f}; "
              f"previous committed spend ${report['collection']['prior_committed_usd']:.8f}; "
              f"known combined ${total + report['collection']['prior_committed_usd']:.8f}. "
              f"Unobserved transport admissions retain ${held:.8f}; conservative combined upper bound "
              f"${total + held + report['collection']['prior_committed_usd']:.8f} within the $2 ceiling.", "",
        f"Explicit empty provider errors normalized to policy-backed zero charge: {report['policy_backed_zero_charge_provider_errors']}. "
        "They remain failed draws. Raw usage and billing provenance are preserved; unknown non-error billing still stops collection.", "",
        "Measured costs include recorded failed responses. Recovery rollouts pay the producer prefix and API predictors pay "
        "their forecasting fee. Admission uses the advance reservation, not future receipts. Policies stop on "
        "public-base success; Plus outcomes never select an action. Direct models do not pay a producer-prefix fee.", "",
        "Two-draw banks constrain every policy: these are not unlimited retry or multi-step controller claims. "
        "Conditional rates average draws per independent failed task. Bootstrap resamples held-out tasks, "
        "4000 times with seed 20261024; secondary comparisons have no multiplicity-adjusted significance claim. "
        "Observed benefit MSE includes two-draw measurement noise and is not error against true individual effects.", "",
        "Distractor fields are character matched; provider token counts are recorded in analysis.json. "
        "The producer and next solvers differ in family/training/precision. Task-level holdout does not remove "
        "possible pretraining contamination of HumanEval+. This remains one benchmark family and one live provider snapshot.", ""]
    lines += [f"Secondary replay-selected fixed actions by budget: {report['development_replay_best_actions']}.",
              f"State-ridge minus this stronger fixed comparator at $0.01/task: "
              f"{report['secondary_state_minus_development_replay_best_utility_usd']}.", ""]
    if report["producer_provider_transfer"]:
        lines += [f"Producer provider changed from `{report['development_producer_endpoint']}` to "
                  f"`{report['evaluation_producer_endpoint']}` before any evaluation response, after rate-limit stops. "
                  "This is a provider-transfer evaluation, not identical-provider IID validation. All five unknown "
                  "admissions remain reserved as collection overhead; no zero-cost receipts or task outcomes are invented. "
                  "Policy replay bills concern the complete observed bank and do not fully identify deployment outage/retry cost.", ""]
    return "\n".join(lines)


def benchmark_local_prediction(data: dict) -> dict:
    """Offline CPU microbenchmark, separately labeled from original collection timing."""
    states = [cp for cp in data["checkpoints"] if cp["split"] == "evaluation"]
    by_call = {c["call"]: c for c in data["calls"]}
    timing = {}
    for view in ("global", "task", "state"):
        start = time.process_time()
        for _ in range(20):
            for cp in states:
                prompt = by_call[cp["parent_call"]]["messages"][0]["content"][len(SYSTEM) + 2:]
                predict(data["policy"], prompt, cp, view)
        operations = 20 * len(states)
        timing[view] = {"predictions": operations,
                        "mean_cpu_ms": 1000 * (time.process_time() - start) / operations if operations else None}
    return {"kind": "offline_replay_microbenchmark_not_live_latency", "measurements": timing,
            "dollar_conversion": None}


def plot(report: dict, output: Path) -> None:
    """Visualize held-out effects and the primary policy comparison without fitting curves."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, grid = plt.subplots(2, 2, figsize=(11, 8.2), layout="constrained")
    axes = grid.ravel()
    labels = ["Fresh", "Code", "Feedback", "Both", "Distractor"]
    x = np.arange(5)
    for model, offset, color in (("small", -0.18, "#4479a2"), ("large", 0.18, "#cf8853")):
        records = [report["conditional_recovery"][model + "." + a] for a in CONDITIONS]
        values = [100 * r["mean"] if r["mean"] is not None else 0 for r in records]
        lower = [max(0, v - 100 * r["bootstrap_95"][0]) if r["bootstrap_95"] else 0 for v, r in zip(values, records)]
        upper = [max(0, 100 * r["bootstrap_95"][1] - v) if r["bootstrap_95"] else 0 for v, r in zip(values, records)]
        axes[0].errorbar(x + offset, values, yerr=[lower, upper], fmt="o", capsize=3,
                         label="9B" if model == "small" else "27B", color=color)
    axes[0].set_xticks(x, labels, rotation=25, ha="right")
    axes[0].set_ylim(0, 105)
    axes[0].set_title("Conditional next-attempt success (%)")
    axes[0].legend(frameon=False)
    chosen = ["direct_small", "direct_large", "best_fixed", "state", "api_state"]
    display = ["9B direct", "27B direct", "Best fixed", "State ridge", "State API"]
    for key, label in zip(chosen, display):
        row = report["policies"]["0.01"][key]
        axes[1].scatter(1000 * row["mean_api_cost_usd"], 100 * row["success_rate"], s=55)
        axes[1].annotate(label, (1000 * row["mean_api_cost_usd"], 100 * row["success_rate"]), xytext=(3, 5), textcoords="offset points", fontsize=8)
    axes[1].set_xlabel("Mean API cost (milli-USD/task)")
    axes[1].set_ylabel("Full held-out success (%)")
    axes[1].set_title("Whole-task policies, $0.01 ceiling")
    names = ["global", "task", "state", "api_task_only", "api_state"]
    axes[2].bar(range(5), [report["forecast_brier"].get(n, {}).get("mean", 0) for n in names], color="#708a81")
    axes[2].set_xticks(range(5), ["Global", "Task ridge", "State ridge", "Task API", "State API"], rotation=30, ha="right")
    axes[2].set_title("Prospective Brier score (lower better)")
    axes[3].bar(range(5), [report["observed_benefit_mse"].get(n, {}).get("mean", 0) for n in names], color="#9b83a1")
    axes[3].set_xticks(range(5), ["Global", "Task ridge", "State ridge", "Task API", "State API"], rotation=30, ha="right")
    axes[3].set_title("MSE of predicted context benefit\nAgainst noisy two-draw differences")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Frozen task holdout: {report['evaluation_tasks']} tasks, {report['evaluation_failed_tasks']} natural failures\n"
                 "Two-draw bank; producer-provider transfer; primary result and uncertainty in report", fontsize=11)
    fig.savefig(output, dpi=180)
    fig.savefig(output.with_suffix(".pdf"))
    plt.close(fig)


def main() -> int:
    """Audit a completed run and write an offline analysis into a fresh directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = audit(Path(args.input))
    report, rows = analyze(data)
    report["local_prediction_timing"] = benchmark_local_prediction(data)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "rollouts.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    (output / "report.md").write_text(markdown(report))
    plot(report, output / "validation.png")
    print(json.dumps({"primary": report["primary"], "evaluation_failed_tasks": report["evaluation_failed_tasks"], "cost_usd": report["collection"]["collection_cost_usd"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
