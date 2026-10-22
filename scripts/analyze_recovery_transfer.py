"""Audit recorded MBPP+ recovery evidence and reproduce the frozen statistical comparisons."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from decimal import Decimal
from pathlib import Path

import numpy as np

from vao.decisions.context_value import ARMS
from vao.decisions.pilot import SYSTEM, digest
from vao.decisions.recovery import CONDITIONS, producer_messages, recovery_messages
from vao.decisions.recovery_policy import features, predict
from vao.decisions.transfer import VIEWS, choose, file_hash, freeze, records, replay, reservation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same(v, b[k]) for k,v in a.items())
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(same(x,y) for x,y in zip(a,b))
    if isinstance(a, (int, float)) and not isinstance(a, bool):
        return isinstance(b, (int,float)) and np.isclose(a, b, atol=1e-12, rtol=1e-10)
    return a == b


def interval(values, alpha=.05):
    v = np.asarray(values, dtype=float)
    require(len(v) > 1, "Need at least two independent tasks for an interval")
    rng = np.random.default_rng(20261025)
    draws = v[rng.integers(0, len(v), size=(10000, len(v)))].mean(axis=1)
    return {"estimate": float(v.mean()), "low": float(np.quantile(draws, alpha/2)),
            "high": float(np.quantile(draws, 1-alpha/2)), "tasks": len(v), "alpha": alpha}


def audit(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    cfg = manifest["config"]
    reference_path = Path(cfg["reference_audit"])
    require(file_hash(reference_path) == cfg["reference_audit_sha256"], "Reference census changed")
    reference = [json.loads(s) for s in reference_path.read_text().splitlines()]
    require(len(reference) == len({r["task_id"] for r in reference}) == 378, "Reference census incomplete/duplicated")
    excluded = [r["task_id"] for r in reference if not r["base_feedback"]["passed"] or not r["heldout"]["passed"]]
    require(sorted(excluded) == sorted(cfg["reference_exclusions"]), "Reference exclusions changed")
    task_order = sorted({r["task_id"] for r in reference} - set(excluded),key=lambda t:int(t.split("/")[1]))
    random.Random(cfg["seed"]).shuffle(task_order)
    require(task_order == manifest["task_order"], "Frozen external task order changed")
    require(Decimal(str(cfg["run_ceiling_usd"])) + Decimal(str(cfg["prior_committed_usd"])) <= Decimal(str(cfg["campaign_ceiling_usd"])), "Declared cap double-spends prior reservations")
    if (root / "checksums.json").exists():
        for name, expected in json.loads((root / "checksums.json").read_text()).items():
            require(file_hash(root/name) == expected, "Curated checksum: " + name)
    saved = json.loads((root / "frozen-policy.json").read_text())
    refit, source = freeze(cfg)
    require(same(saved, refit), "Frozen source policy cannot be reproduced")
    require(digest(saved) == manifest["policy_sha256"], "Frozen weight hash changed")
    require(digest(saved) == cfg["source_policy_digest"], "Weights differ from prospective config")
    calls = records(root, "calls")
    call_by_id = {r["call"]: r for r in calls}
    require(len(calls) == len(call_by_id), "Duplicated response identity")
    require(len({r["generation_id"] for r in calls}) == len(calls), "Duplicated provider generation identity")
    ledger = records(root, "budget")
    reserves, settlements = {}, {}
    for r in ledger:
        c = r["call"]
        if r["event"] == "reserve":
            require(c not in reserves, "Repeated admission")
            reserves[c] = Decimal(str(r["reserved_usd"]))
        elif r["event"] == "settle":
            require(c in reserves and c not in settlements, "Settlement without unique admission")
            settlements[c] = Decimal(str(r["cost_usd"]))
            require(0 <= settlements[c] <= reserves[c], "Over-reservation charge")
        else:
            raise ValueError("Unexpected budget event")
        committed = sum(settlements.values()) + sum(v for k,v in reserves.items() if k not in settlements)
        require(committed <= Decimal(str(cfg["run_ceiling_usd"])), "Collection budget exceeded")
    require(set(settlements) == set(call_by_id), "Response/settlement census differs")
    for c,r in call_by_id.items():
        require(Decimal(str(r["usage"]["cost"])) == settlements[c], "Receipt differs from settlement")
        require(reserves[c] == reservation(cfg,r["model_name"]), "Wrong advance reservation")
        require(r["model"] == cfg["models"][r["model_name"]]["id"], "Unplanned model")
        require(r["returned_model"] == r["model"], "Returned model differs from request")
        require(r["provider"].lower() == cfg["models"][r["model_name"]].get("provider_name", "SiliconFlow").lower(), "Unplanned provider")
        require(r.get("seed_sent") is None, "Sampler seed differs from protocol")
        require(not (r["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens",0), "Unexpected reasoning tokens")
    initial = records(root, "initial")
    require([r["task_id"] for r in initial] == manifest["task_order"][:len(initial)], "Initial task selection/order drift")
    require(len({r["task_id"] for r in initial}) == len(initial), "Repeated initial task")
    prompts = {}
    for r in initial:
        c = call_by_id[r["call"]]
        require(c["action"] == "initial" and c["model_name"] == "producer", "Unplanned producer")
        content = c["messages"][0]["content"]
        require(content.startswith(SYSTEM + "\n\n"), "Producer prompt changed")
        prompts[r["task_id"]] = content[len(SYSTEM + "\n\n"):]
        require(digest(prompts[r["task_id"]]) == manifest["prompt_sha256"][r["task_id"]], "Task prompt hash")
        require(c["messages"] == producer_messages({"prompt": prompts[r["task_id"]]}), "Producer projection")
    cp_list = records(root, "checkpoints")
    cps = {c["checkpoint_id"]: c for c in cp_list}
    require(len(cps) == len(cp_list), "Duplicate checkpoints")
    require([c["parent_call"] for c in cp_list] == [r["call"] for r in initial if not r["visible_passed"]], "Not the full public-failure census")
    evals = {r["call"]: r for r in records(root, "evaluations")}
    require(set(evals) == set(call_by_id), "Response/evaluation census differs")
    for r in initial:
        e = evals[r["call"]]
        require(r["passed"] == e["heldout"]["passed"] and r["visible_passed"] == e["visible"]["passed"], "Initial outcome mismatch")
        require(Decimal(str(r["cost_usd"])) == settlements[r["call"]], "Initial cost mismatch")
    for c in cp_list:
        e = evals[c["parent_call"]]
        require(c["solution"] == e["solution"] and digest(c["solution"]) == c["solution_sha256"], "Artifact mismatch")
        require(c["feedback"] == e["visible"] and not c["feedback"]["passed"], "Private selection/feedback drift")
        require(Decimal(str(c["prefix_cost_usd"])) == settlements[c["parent_call"]], "Prefix cost mismatch")
    selection = json.loads((root / "selection.json").read_text())
    selected = selection["selected_checkpoint_ids"]
    require(selected == [c["checkpoint_id"] for c in cp_list[:cfg["maximum_checkpoints"]]], "Recovery selection drift")
    require(len(initial) == len(manifest["task_order"]), "Initial census is incomplete; no confirmatory result")
    require(selection["last_admitted_call"] == max(r["call"] for r in initial), "Selection boundary changed")
    predictions = records(root, "local-predictions")
    pred = {r["checkpoint_id"]: r for r in predictions}
    require(list(pred) == selected, "Predictions not saved for every selected failure")
    donors = sorted(source["checkpoints"], key=lambda c: c["task_id"])
    branches = records(root, "branches")
    require({r["call"] for r in initial} | {r["call"] for r in branches} == set(call_by_id), "Missing or extra scored call")
    cells = Counter()
    for r in branches:
        c, cp = call_by_id[r["call"]], cps[r["checkpoint_id"]]
        require(r["checkpoint_id"] in selected and r["arm"] in CONDITIONS, "Unplanned branch")
        require(r["model_name"] in cfg["target_models"] and 0 <= r["draw"] < cfg["branch_repeats"], "Unplanned cell")
        key = (r["checkpoint_id"], r["model_name"], r["arm"], r["draw"])
        cells[key] += 1
        require(cells[key] == 1, "Repeated draw")
        donor = donors[int(cp["task_id"].split("/")[1]) % len(donors)]
        require(c["messages"] == recovery_messages({"prompt": prompts[r["task_id"]]}, r["arm"], cp, donor), "Branch prompt leaks or drifts")
        require(r["donor_checkpoint_id"] == (donor["checkpoint_id"] if r["arm"] == "distractor" else None), "Donor drift")
        require(all(c[k] == r[k] for k in ("task_id", "checkpoint_id", "parent_call", "model_name", "arm", "draw")), "Call/branch identity mismatch")
        e = evals[r["call"]]
        require(r["passed"] == e["heldout"]["passed"] and r["visible_passed"] == e["visible"]["passed"], "Branch outcome mismatch")
        require(Decimal(str(r["incremental_cost_usd"])) == settlements[r["call"]], "Branch cost mismatch")
        require(c["call"] > selection["last_admitted_call"], "Branch observed before selection")
    for id_, r in pred.items():
        require(r["policy_sha256"] == manifest["policy_sha256"], "Prediction weights changed")
        require(r["last_admitted_call"] == selection["last_admitted_call"], "Prediction not prospective")
        cp = cps[id_]
        expected = {v: predict(saved, prompts[cp["task_id"]], cp, v) for v in ("global", *VIEWS)}
        require(same(r["probabilities"], expected), "Prediction cannot be reproduced")
    blocks = records(root, "blocks")
    complete = [b["checkpoint_id"] for b in blocks]
    require(complete == selected[:len(complete)], "Complete blocks are not an ordered prefix")
    for id_ in complete:
        require(sum(k[0] == id_ for k in cells) == len(CONDITIONS) * len(cfg["target_models"]) * cfg["branch_repeats"], "Incomplete declared block")
    # Reconstruct each complete-block admission from the budget journal, before
    # seeing any of that block's eventual receipts or outcomes.
    first_calls = {min(r["call"] for r in branches if r["checkpoint_id"] == id_): id_
                   for id_ in selected if any(r["checkpoint_id"] == id_ for r in branches)}
    block_ceiling = sum(reservation(cfg,m)*len(CONDITIONS)*cfg["branch_repeats"] for m in cfg["target_models"])
    prior_spent, pending_costs = Decimal(0), {}
    for r in ledger:
        c = r["call"]
        if r["event"] == "reserve":
            if c in first_calls:
                require(prior_spent + sum(pending_costs.values()) + block_ceiling <= Decimal(str(cfg["run_ceiling_usd"])), "Block was not fully affordable at admission")
            pending_costs[c] = Decimal(str(r["reserved_usd"]))
        else:
            pending_costs.pop(c)
            prior_spent += Decimal(str(r["cost_usd"]))
    known = sum(settlements.values())
    held = sum(v for k,v in reserves.items() if k not in settlements)
    total = known + held + Decimal(str(cfg["prior_committed_usd"]))
    require(total <= Decimal(str(cfg["campaign_ceiling_usd"])), "Campaign ceiling exceeded")
    return {"config": cfg, "manifest": manifest, "policy": saved, "source": source, "calls": call_by_id,
        "initial": initial, "checkpoints": cps, "predictions": pred, "prompts": prompts,
        "branches": branches, "selected": selected, "complete": complete, "evaluations": evals,
        "collection": {"admissions": len(reserves), "responses": len(calls), "known_cost_usd": float(known),
            "unresolved_reservations_usd": float(held), "prior_upper_usd": cfg["prior_committed_usd"],
            "campaign_upper_usd": float(total)}}


def variance_stat(d):
    """Cross-draw product minus cross-task squared mean; can be negative with noise."""
    d = np.asarray(d, dtype=float)
    n,r = d.shape
    within = ((d.sum(axis=1)**2 - (d*d).sum(axis=1)) / (r*(r-1))).mean()
    m = d.mean(axis=1)
    mean_squared = (m.sum()**2 - (m*m).sum()) / (n*(n-1))
    return float(within - mean_squared)


def analyze(data):
    cfg, policy = data["config"], data["policy"]
    ids = data["complete"]
    require(len(ids) > 1, "Too few complete failed tasks")
    grouped = {id_: [r for r in data["branches"] if r["checkpoint_id"] == id_] for id_ in ids}
    rates, effects = {}, {}
    loss, benefit_loss, differences = {v: [] for v in ("global", *VIEWS)}, {v: [] for v in ("global", *VIEWS)}, {}
    for model in cfg["target_models"]:
        rates[model] = {}
        arrays = {}
        for arm in CONDITIONS:
            rows = [r for id_ in ids for r in grouped[id_] if r["model_name"] == model and r["arm"] == arm]
            values = [np.mean([r["passed"] for r in grouped[id_] if r["model_name"] == model and r["arm"] == arm]) for id_ in ids]
            arrays[arm] = np.array([[r["passed"] for r in sorted(grouped[id_],key=lambda x:x["draw"])
                if r["model_name"] == model and r["arm"] == arm] for id_ in ids], dtype=float)
            calls = [data["calls"][r["call"]] for r in rows]
            tokens = [c["usage"]["prompt_tokens"] for c in calls if c["usage"].get("prompt_tokens") is not None]
            outtokens = [c["usage"]["completion_tokens"] for c in calls if c["usage"].get("completion_tokens") is not None]
            rates[model][arm] = {"success": interval(values), "draws": len(rows), "cost_usd": float(np.mean([r["incremental_cost_usd"] for r in rows])),
                "mean_input_tokens": float(np.mean(tokens)) if tokens else None, "mean_output_tokens": float(np.mean(outtokens)) if outtokens else None,
                "token_receipts": len(tokens)}
        effects[model] = {}
        for a,b in (("artifact","fresh"),("artifact_feedback","fresh"),("artifact_feedback","feedback"),("artifact_feedback","distractor")):
            diff = arrays[a] - arrays[b]
            effects[model][a+"-"+b] = {"ordinary_95": interval(diff.mean(axis=1)), "simultaneous_99_375": interval(diff.mean(axis=1), .05/8)}
            if b in {"feedback", "fresh"}:
                differences[model+":"+b] = diff
    for id_ in ids:
        rows = grouped[id_]
        for view in loss:
            p = data["predictions"][id_]["probabilities"][view]
            loss[view].append(np.mean([(p[r["model_name"]+"."+r["arm"]] - r["passed"])**2 for r in rows if r["arm"] in ARMS]))
            errors = []
            for m in cfg["target_models"]:
                for b in ("feedback","fresh"):
                    observed = np.mean([r["passed"] for r in rows if r["model_name"] == m and r["arm"] == "artifact_feedback"]) - np.mean([r["passed"] for r in rows if r["model_name"] == m and r["arm"] == b])
                    errors.append((p[m+".artifact_feedback"] - p[m+"."+b] - observed)**2)
            benefit_loss[view].append(np.mean(errors))
    policies = ["global", "task", "feedback", "state", "state_model_only", "best_static", "direct_small", "direct_large"] + ["fixed:"+k for k in policy["priors"]]
    rollouts = []
    for budget in cfg["task_budgets_usd"]:
        for rotation in range(cfg["branch_repeats"]):
            for name in policies:
                for id_ in ids:
                    cp = data["checkpoints"][id_]
                    p = data["predictions"][id_]["probabilities"]
                    include_prefix = not name.startswith("direct_")
                    if name.startswith("fixed:"):
                        action = name.split(":",1)[1]
                    elif name == "best_static":
                        action = policy["development_replay_fixed"][str(budget)]
                    elif name.startswith("direct_"):
                        action = name.removeprefix("direct_") + ".fresh"
                    else:
                        action = choose(policy, p["state" if name == "state_model_only" else name], cfg, budget,
                                        cp["prefix_cost_usd"], "model_only" if name == "state_model_only" else None)
                    # Primary rotation 0 uses draws (0,1); others are prespecified sensitivity checks.
                    rows = [dict(r, draw=(r["draw"]-rotation) % cfg["branch_repeats"]) for r in grouped[id_]]
                    out = replay(rows, action, cp["prefix_cost_usd"], cfg, budget, include_prefix=include_prefix)
                    rollouts.append({"checkpoint_id": id_, "task_id": cp["task_id"], "policy": name, "budget_usd": budget,
                        "rotation": rotation, "selected_action": action, **out, "net_utility_usd": .01*out["passed"] - out["cost_usd"]})
    summaries = {}
    for budget in cfg["task_budgets_usd"]:
        summaries[str(budget)] = {}
        for name in policies:
            rows = [r for r in rollouts if r["policy"] == name and r["budget_usd"] == budget and r["rotation"] == 0]
            summaries[str(budget)][name] = {"success": float(np.mean([r["passed"] for r in rows])),
                "cost_usd": float(np.mean([r["cost_usd"] for r in rows])), "net_utility_usd": float(np.mean([r["net_utility_usd"] for r in rows])),
                "selected_actions": dict(Counter(r["selected_action"] or "abstain" for r in rows))}
    comparisons = {}
    for rotation in range(cfg["branch_repeats"]):
        comparisons[str(rotation)] = {}
        for control in ("feedback", "best_static", "state_model_only", "task", "global"):
            a = [r for r in rollouts if r["policy"] == "state" and r["budget_usd"] == .01 and r["rotation"] == rotation]
            b = [r for r in rollouts if r["policy"] == control and r["budget_usd"] == .01 and r["rotation"] == rotation]
            comparisons[str(rotation)][control] = {k: interval([float(x[k])-float(y[k]) for x,y in zip(a,b)])
                for k in ("net_utility_usd", "passed", "cost_usd")}
    heterogeneity = {}
    rng = np.random.default_rng(20261025)
    resamples = rng.integers(0,len(ids),size=(10000,len(ids)))
    for key,d in differences.items():
        bootstrap = np.array([variance_stat(d[idx]) for idx in resamples])
        heterogeneity[key] = {"unclipped_variance": variance_stat(d), "low": float(np.quantile(bootstrap,.025)), "high": float(np.quantile(bootstrap,.975))}
    featureshift = {}
    for k in features("", data["checkpoints"][ids[0]]):
        train = [features(data["source"]["prompts"][c["task_id"]],c)[k] for c in data["source"]["checkpoints"]]
        test = [features(data["prompts"][data["checkpoints"][id_]["task_id"]],data["checkpoints"][id_])[k] for id_ in ids]
        featureshift[k] = {"source_mean": float(np.mean(train)), "target_mean": float(np.mean(test)), "outside_source_range": sum(x < min(train) or x > max(train) for x in test)}
    selected, complete = len(data["selected"]), len(ids)
    primary = comparisons["0"]["feedback"]["net_utility_usd"]
    # A conservative missing-state bound: each policy's net utility lies in
    # [-budget, value], hence their paired difference is in [-(budget+value), +(budget+value)].
    incomplete_bound = None
    if selected > complete:
        incomplete_bound = {"low": (complete*primary["estimate"]-(selected-complete)*.02)/selected,
                            "high": (complete*primary["estimate"]+(selected-complete)*.02)/selected}
    report = {"status": "complete_confirmatory_bank" if selected == complete else "incomplete_descriptive_bank",
        "primary": primary, "selected_states": selected, "complete_states": complete, "missing_state_utility_bounds": incomplete_bound,
        "initial_tasks": len(data["initial"]), "initial_public_failures": len(data["checkpoints"]),
        "initial_full_successes": sum(r["passed"] for r in data["initial"]),
        "initial_public_false_positives": sum(r["visible_passed"] and not r["passed"] for r in data["initial"]),
        "collection": data["collection"], "rates": rates, "effects": effects, "policy_summary": summaries,
        "policy_comparisons": comparisons, "brier": {v:float(np.mean(x)) for v,x in loss.items()},
        "benefit_mse": {v:float(np.mean(x)) for v,x in benefit_loss.items()},
        "state_feedback_brier_difference": interval(np.array(loss["state"])-loss["feedback"]),
        "state_feedback_benefit_mse_difference": interval(np.array(benefit_loss["state"])-benefit_loss["feedback"]),
        "latent_benefit_variance_diagnostic": heterogeneity, "feature_shift": featureshift,
        "failure_statuses": dict(Counter(str(e["visible"]["status"]) for e in data["evaluations"].values())),
        "branch_public_false_positives": sum(r["visible_passed"] and not r["passed"] for r in data["branches"]),
        "explicit_provider_errors": sum(r.get("finish_reason") == "error" for r in data["calls"].values())}
    return report, rollouts


def markdown(r):
    p = r["primary"]
    lines = ["# MBPP+ recovery replication", "", f"Status: **{r['status']}**. {r['initial_tasks']} initial tasks; "
        f"{r['initial_public_failures']} public failures; {r['complete_states']}/{r['selected_states']} selected states complete.", "",
        "The primary is state minus feedback-only policy net utility at the $0.01 task ceiling, original draws 0 and 1.", "",
        f"Estimate **${p['estimate']:+.8f}/failure**, task-bootstrap 95% interval **[${p['low']:+.8f}, ${p['high']:+.8f}]**.", "",
        "An interval spanning zero does not establish equivalence or an improvement. Complete-case intervals are descriptive if the bank is incomplete.", "",
        "## Conditional single-draw success", "", "| Model | Fresh | Code | Feedback | Both | Distractor |", "|---|---:|---:|---:|---:|---:|"]
    for m, arms in r["rates"].items():
        lines.append("| " + m + " | " + " | ".join(f"{100*arms[a]['success']['estimate']:.1f}%" for a in CONDITIONS) + " |")
    lines += ["", "## Prespecified context contrasts", "", "All effects are percentage points. Simultaneous intervals cover the family of eight contrasts by Bonferroni.", "",
        "| Model | Contrast | Effect | 95% | Simultaneous 99.375% |", "|---|---|---:|---:|---:|"]
    for m, effects in r["effects"].items():
        for name, pair in effects.items():
            a,b = pair["ordinary_95"],pair["simultaneous_99_375"]
            lines.append(f"| {m} | {name} | {100*a['estimate']:+.1f} | [{100*a['low']:+.1f}, {100*a['high']:+.1f}] | [{100*b['low']:+.1f}, {100*b['high']:+.1f}] |")
    lines += ["", "## Two-draw policies at $0.01", "", "Conditional on the sampled failed prefix. Direct controls omit producer cost and refer only to this failure population.", "",
              "| Policy | Success | Mean API dollars | Net utility |", "|---|---:|---:|---:|"]
    for name, row in r["policy_summary"]["0.01"].items():
        lines.append(f"| {name} | {100*row['success']:.1f}% | ${row['cost_usd']:.8f} | ${row['net_utility_usd']:.8f} |")
    lines += ["", "## Prediction and limitations", "", "| View | Brier | Observed benefit MSE |", "|---|---:|---:|"]
    for v in r["brier"]:
        lines.append(f"| {v} | {r['brier'][v]:.6f} | {r['benefit_mse'][v]:.6f} |")
    lines += ["", f"State-feedback benefit-MSE difference: `{r['state_feedback_benefit_mse_difference']}`.", "",
        f"Initial public false positives: {r['initial_public_false_positives']}; branch false positives: {r['branch_public_false_positives']}; explicit provider errors: {r['explicit_provider_errors']}.", "",
        f"Collection accounting: `{r['collection']}`.", "",
        "This is one benchmark/producer/provider pair and one checkpoint. Cheap structural artifact features do not exhaust semantic artifact value. Task lengths shift across benchmarks. Character-matched distractors are not token-matched; see token receipts in analysis.json. Model pretraining contamination cannot be ruled out. No general multi-step controller or CodeRescue reproduction is established.", "",
        "The former HumanEval+ evaluation is now training data for this replica. Keep its earlier frozen evaluation result separate. Sensitivity rotations, all budgets/actions, noisy-benefit diagnostics and feature shifts are in analysis.json. No secondary test is substituted for the primary.", ""]
    if r["missing_state_utility_bounds"]:
        lines += [f"Missing selected-state worst-case utility bounds: `{r['missing_state_utility_bounds']}`.", ""]
    return "\n".join(lines)


def plot(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots(1,2,figsize=(12,4.5),layout="constrained")
    labels, points, lows, highs = [],[],[],[]
    for m in r["effects"]:
        for name,pair in r["effects"][m].items():
            a = pair["simultaneous_99_375"]
            labels.append(m+" / "+name.replace("artifact_feedback","both").replace("artifact","code"))
            points.append(100*a["estimate"]); lows.append(100*(a["estimate"]-a["low"])); highs.append(100*(a["high"]-a["estimate"]))
    y = np.arange(len(labels))
    ax[0].errorbar(points,y,xerr=[lows,highs],fmt="o",capsize=3)
    ax[0].axvline(0,color="gray",lw=1); ax[0].set_yticks(y,labels,fontsize=8); ax[0].invert_yaxis()
    ax[0].set_xlabel("Success difference (percentage points)"); ax[0].set_title("Context contrasts: simultaneous intervals")
    names = ["best_static", "feedback", "state", "state_model_only", "direct_small", "direct_large"]
    for name in names:
        row=r["policy_summary"]["0.01"][name]
        ax[1].scatter(row["cost_usd"]*1000,row["success"]*100,label=name)
    ax[1].set_xlabel("Mean API dollars × 1,000"); ax[1].set_ylabel("Conditional recovery success (%)")
    ax[1].set_title("Two-draw replay at $0.01"); ax[1].legend(fontsize=8)
    fig.suptitle(f"MBPP+ replication: {r['complete_states']} independent failed tasks")
    fig.savefig(path,dpi=180); fig.savefig(path.with_suffix(".pdf")); plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    data=audit(args.input)
    report,rollouts=analyze(data)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/"analysis.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    (args.output/"rollouts.jsonl").write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rollouts))
    (args.output/"report.md").write_text(markdown(report))
    plot(report,args.output/"replication.png")
    print(json.dumps({"status":report["status"],"primary":report["primary"],"collection":report["collection"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
