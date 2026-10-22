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
from vao.decisions.transfer import VIEWS, choose, file_hash, freeze, records, replay, replay_escalation,reservation


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


def recovery_lineages(root):
    current=root/"recovery-continuation.json"
    index=root/"recovery-continuation-history.json"
    if not current.exists():
        require(not index.exists(),"Orphan recovery lineage index")
        return []
    history=json.loads(index.read_text()) if index.exists() else []
    lineages=[];paths=set()
    for entry in history:
        path=Path(entry["path"])
        require(not path.is_absolute() and ".." not in path.parts and path.parts[0]=="recovery-history","Recovery history path escaped archive")
        require(str(path) not in paths,"Repeated history entry");paths.add(str(path))
        require(file_hash(root/path)==entry["sha256"],"Archived recovery lineage changed")
        lineages.append(json.loads((root/path).read_text()))
    lineages.append(json.loads(current.read_text()))
    boundaries=[r["imported_last_admitted_call"] for r in lineages]
    require(all(a<b for a,b in zip(boundaries,boundaries[1:])),"Recovery segment boundaries are not increasing")
    for i,r in enumerate(lineages):
        require(r.get("previous_lineages",[])==history[:i],"Recovery parent history changed")
    return lineages


def audit(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text())
    cfg = manifest["config"]
    continuation=json.loads((root/"prefix-continuation.json").read_text()) if (root/"prefix-continuation.json").exists() else None
    lineages=recovery_lineages(root)
    recovery_continuation=lineages[-1] if lineages else None
    authorization_path=Path("experiments/mbpp-plus/context-value-transfer/configs/recovery-continuation-freeze.json")
    original_authorization=json.loads(authorization_path.read_text()) if lineages else None
    for i,recovery_segment in enumerate(lineages):
        import hashlib
        require(recovery_segment["source_manifest_sha256"]==file_hash(root/"manifest.json"),"Recovery continuation identity changed")
        freeze_path=Path(recovery_segment.get("authorization_freeze_path") or authorization_path)
        require(freeze_path.resolve().is_relative_to(authorization_path.parent.resolve()),"Segment freeze escaped config directory")
        frozen=json.loads(freeze_path.read_text())
        if recovery_segment.get("authorization_freeze_sha256"):
            require(file_hash(freeze_path)==recovery_segment["authorization_freeze_sha256"],"Segment freeze changed")
        require(recovery_segment["source_hashes"]==frozen["approved_source_sha256"],"Approved source hashes changed")
        require(recovery_segment["source_summary"]==frozen["source_summary"],"Recorded stop summary differs from segment freeze")
        require(recovery_segment["authorization"]==frozen["authorization"]==original_authorization["authorization"],"Root authorization changed")
        require(recovery_segment["authorized_unadmitted_cells"]==frozen["authorized_unadmitted_cells"],"Authorized segment cell list changed")
        require({tuple(k) for k in frozen["authorized_unadmitted_cells"]}<={tuple(k) for k in original_authorization["authorized_unadmitted_cells"]},"Segment exceeds root authorized cell set")
        require(recovery_segment["source_collector_sha256"]==frozen["continuation_source_sha256"],"Segment collector differs from freeze")
        if i:
            require(frozen["root_authorization_freeze_sha256"]==file_hash(authorization_path),"Root authorization freeze changed")
        for name,count in recovery_segment["imported_line_counts"].items():
            prefix=b"".join((root/name).read_bytes().splitlines(keepends=True)[:count])
            require(hashlib.sha256(prefix).hexdigest()==recovery_segment["source_hashes"][name],"Imported recovery evidence changed: "+name)
        for name,expected in recovery_segment["source_hashes"].items():
            archived=recovery_segment.get("imported_static_archives",{}).get(name)
            if archived:
                path=Path(archived)
                require(not path.is_absolute() and ".." not in path.parts and path.parts[0]=="recovery-history","Static history path escaped archive")
                require(file_hash(root/path)==expected,"Archived static recovery evidence changed: "+name)
            elif name=="recovery-continuation.json":
                require(i>0 and expected==recovery_segment["previous_lineages"][-1]["sha256"],"Previous lineage bytes changed")
            elif name.endswith(".json") and name not in {"summary.json","checksums.json","recovery-continuation-history.json"}:
                require(file_hash(root/name)==expected,"Imported static recovery evidence changed: "+name)
    censored=[continuation["censored_prefix"]] if continuation else []
    censored_tasks={r["task_id"] for r in censored}
    if continuation:
        require(continuation["source_manifest_sha256"]==file_hash(root/"manifest.json"),"Original experimental identity changed")
        counts={"calls.jsonl":continuation["imported_observed_prefixes"],"initial.jsonl":continuation["imported_observed_prefixes"],
            "evaluations.jsonl":continuation["imported_observed_prefixes"],"checkpoints.jsonl":continuation["imported_checkpoints"],
            "budget.jsonl":continuation["imported_budget_events"],"transport.jsonl":1}
        import hashlib
        for name,count in counts.items():
            prefix=b"".join((root/name).read_bytes().splitlines(keepends=True)[:count])
            require(hashlib.sha256(prefix).hexdigest()==continuation["source_hashes"][name],"Imported evidence changed: "+name)
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
    observed_order=[t for t in manifest["task_order"] if t not in censored_tasks]
    require([r["task_id"] for r in initial] == observed_order[:len(initial)], "Initial task selection/order drift")
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
    require(len(initial)+len(censored) == len(manifest["task_order"]), "Initial census has unaccounted missing tasks")
    if censored:
        require(continuation["selected_checkpoint_ids_unchanged"]==selected,"Selected cohort changed during continuation")
        missing=censored[0]
        require(missing["call"] in reserves and missing["call"] not in settlements and missing["action"]=="initial", "Censored prefix lost its full reservation")
        require(all(manifest["task_order"].index(cps[id_]["task_id"])<manifest["task_order"].index(missing["task_id"]) for id_ in selected), "Censored prefix could change selected failures")
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
    branch_censors=[r for r in records(root,"transport") if r["action"]=="branch"]
    require(len({(r["checkpoint_id"],r["model_name"],r["arm"],r["draw"]) for r in branch_censors})==len(branch_censors),"Uncertain recovery cell was admitted twice")
    transport=records(root,"transport")
    require(len({r["call"] for r in transport})==len(transport),"Repeated uncertain admission identity")
    require(set(reserves)-set(settlements)=={r["call"] for r in transport},"Unexplained unresolved reservations")
    for r in branch_censors:
        require(r["call"] in reserves and r["call"] not in settlements,"Censored recovery lost full reservation")
        require(r["checkpoint_id"] in selected and r["model_name"] in cfg["target_models"] and r["arm"] in CONDITIONS and 0<=r["draw"]<cfg["branch_repeats"],"Unplanned censored recovery")
        require(not cells.get((r["checkpoint_id"],r["model_name"],r["arm"],r["draw"]),0),"Uncertain recovery cell was reissued")
        require(reserves[r["call"]]==reservation(cfg,r["model_name"]),"Censored recovery reservation changed")
    for recovery_segment in lineages:
        require(recovery_segment["selected_checkpoint_ids_unchanged"]==selected,"Recovery continuation changed selected states")
        authorized={tuple(k) for k in recovery_segment["authorized_unadmitted_cells"]}
        for r in branches+branch_censors:
            if r["call"]>recovery_segment["imported_last_admitted_call"]:
                require((r["checkpoint_id"],r["model_name"],r["arm"],r["draw"]) in authorized,"Unapproved continuation request")
    blocks = records(root, "blocks")
    complete = [b["checkpoint_id"] for b in blocks]
    allowed=[id_ for id_ in selected if not recovery_continuation or id_ not in {r["checkpoint_id"] for r in branch_censors}]
    require(complete == allowed[:len(complete)], "Complete blocks are not an ordered prefix of noncensored states")
    for id_ in complete:
        require(sum(k[0] == id_ for k in cells) == len(CONDITIONS) * len(cfg["target_models"]) * cfg["branch_repeats"], "Incomplete declared block")
    # Reconstruct each complete-block admission from the budget journal, before
    # seeing any of that block's eventual receipts or outcomes.
    admitted=branches+branch_censors
    first_calls = {min(r["call"] for r in admitted if r["checkpoint_id"] == id_): id_
                   for id_ in selected if any(r["checkpoint_id"] == id_ for r in admitted)}
    for recovery_segment in lineages:
        # A resumed partial block passes the same whole-block gate again.
        for id_ in selected:
            new=[r["call"] for r in admitted if r["checkpoint_id"]==id_ and r["call"]>recovery_segment["imported_last_admitted_call"]]
            if new:first_calls[min(new)]=id_
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
    return {"config": cfg, "manifest": manifest,"manifest_sha256":file_hash(root/"manifest.json"), "policy": saved, "source": source, "calls": call_by_id,
        "initial": initial, "checkpoints": cps, "predictions": pred, "prompts": prompts,
        "branches": branches, "selected": selected, "complete": complete, "evaluations": evals,
        "censored_branch_requests":branch_censors,"recovery_continuation":recovery_continuation,
        "recovery_lineages":lineages,
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
    rates, effects, model_deltas = {}, {}, {}
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
                "token_receipts": len(tokens),"finish_reasons":dict(Counter(c["finish_reason"] or "missing" for c in calls)),
                "format_failures":sum(data["evaluations"][c["call"]]["visible"]["status"]=="format_error" for c in calls),
                "public_false_positives":sum(r["visible_passed"] and not r["passed"] for r in rows)}
        effects[model] = {}
        model_deltas[model] = {}
        for a,b in (("artifact","fresh"),("artifact_feedback","fresh"),("artifact_feedback","feedback"),("artifact_feedback","distractor")):
            diff = arrays[a] - arrays[b]
            model_deltas[model][a+"-"+b] = diff.mean(axis=1)
            effects[model][a+"-"+b] = {"ordinary_95": interval(diff.mean(axis=1)), "simultaneous_99_583": interval(diff.mean(axis=1), .05/12)}
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
    policies = ["global", "task", "feedback", "state", "state_model_only", "best_static", "direct_small", "direct_large","escalation_diagnostic"] + ["fixed:"+k for k in policy["priors"]]
    rollouts = []
    for budget in cfg["task_budgets_usd"]:
        for rotation in range(cfg["branch_repeats"]):
            for name in policies:
                for id_ in ids:
                    cp = data["checkpoints"][id_]
                    p = data["predictions"][id_]["probabilities"]
                    include_prefix = not name.startswith("direct_")
                    if name=="escalation_diagnostic":
                        action="small.fresh->large.fresh"
                    elif name.startswith("fixed:"):
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
                    out = (replay_escalation(rows,cp["prefix_cost_usd"],cfg,budget) if name=="escalation_diagnostic"
                           else replay(rows, action, cp["prefix_cost_usd"], cfg, budget, include_prefix=include_prefix))
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
        for control in ("feedback", "best_static", "state_model_only", "task", "global","escalation_diagnostic"):
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
    interactions={name:{"ordinary_95":interval(model_deltas["small"][name]-model_deltas["large"][name]),
        "simultaneous_99_583":interval(model_deltas["small"][name]-model_deltas["large"][name],.05/12)} for name in model_deltas["small"]}
    report = {"status": "complete_confirmatory_bank" if selected == complete else "incomplete_descriptive_bank",
        "primary": primary, "selected_states": selected, "complete_states": complete, "missing_state_utility_bounds": incomplete_bound,
        "initial_tasks": len(data["initial"]), "initial_public_failures": len(data["checkpoints"]),
        "initial_eligible_tasks":len(data["manifest"]["task_order"]),"initial_censored_tasks":len(data["manifest"]["task_order"])-len(data["initial"]),
        "initial_full_successes": sum(r["passed"] for r in data["initial"]),
        "initial_public_false_positives": sum(r["visible_passed"] and not r["passed"] for r in data["initial"]),
        "collection": data["collection"], "rates": rates, "effects": effects, "model_context_interactions":interactions,"policy_summary": summaries,
        "censored_branch_requests":data["censored_branch_requests"],
        "recovery_continuation_note":"Human-authorized continuation after a transport stop and partial descriptive audit; only never-admitted cells. Original estimands/weights fixed, but bank remains incomplete and intervals descriptive." if data["recovery_continuation"] else None,
        "escalation_note":"Fixed 9B-fresh then 27B-fresh, added after recovery collection began. Diagnostic only, no target-outcome fitting or change to primary. Both requests use original checkpoint, no new child handoff.",
        "policy_comparisons": comparisons, "brier": {v:float(np.mean(x)) for v,x in loss.items()},
        "benefit_mse": {v:float(np.mean(x)) for v,x in benefit_loss.items()},
        "state_feedback_brier_difference": interval(np.array(loss["state"])-loss["feedback"]),
        "state_feedback_benefit_mse_difference": interval(np.array(benefit_loss["state"])-benefit_loss["feedback"]),
        "latent_benefit_variance_diagnostic": heterogeneity, "feature_shift": featureshift,
        "failure_statuses": dict(Counter(str(e["visible"]["status"]) for e in data["evaluations"].values())),
        "branch_public_false_positives": sum(r["visible_passed"] and not r["passed"] for r in data["branches"]),
        "selected_state_statuses":dict(Counter(str(data["checkpoints"][id_]["feedback"]["status"]) for id_ in data["selected"])),
        "selected_nonempty_artifacts":sum(bool(data["checkpoints"][id_]["solution"].strip()) for id_ in data["selected"]),
        "selected_syntax_valid_artifacts":sum(bool(features(data["prompts"][data["checkpoints"][id_]["task_id"]],data["checkpoints"][id_])["syntax_valid"]) for id_ in data["selected"]),
        "verifier_elapsed_seconds_sum":sum(e["verifier_seconds"] for e in data["evaluations"].values()),
        "verifier_elapsed_seconds_median":float(np.median([e["verifier_seconds"] for e in data["evaluations"].values()])),
        "note_verifier_time":"Sum of per-candidate elapsed times; concurrent workers mean this is not pipeline wall time, CPU time or a monetary charge.",
        "explicit_provider_errors": sum(r.get("finish_reason") == "error" for r in data["calls"].values())}
    return report, rollouts


def markdown(r):
    p = r["primary"]
    lines = ["# MBPP+ recovery replication", "", f"Status: **{r['status']}**. {r['initial_tasks']} initial tasks; "
        f"{r['initial_public_failures']} public failures; {r['complete_states']}/{r['selected_states']} selected states complete.", "",
        f"Initial census: {r['initial_tasks']} observed responses and {r['initial_censored_tasks']} censored admission among {r['initial_eligible_tasks']} eligible tasks. The late censored prefix cannot change the already-observed selected cohort.","",
        "The primary is state minus feedback-only policy net utility at the $0.01 task ceiling, original draws 0 and 1.", "",
        f"Estimate **${p['estimate']:+.8f}/failure**, task-bootstrap 95% interval **[${p['low']:+.8f}, ${p['high']:+.8f}]**.", "",
        "An interval spanning zero does not establish equivalence or an improvement. Complete-case intervals are descriptive if the bank is incomplete.", "",
        "## Conditional single-draw success", "", "| Model | Fresh | Code | Feedback | Both | Distractor |", "|---|---:|---:|---:|---:|---:|"]
    for m, arms in r["rates"].items():
        lines.append("| " + m + " | " + " | ".join(f"{100*arms[a]['success']['estimate']:.1f}%" for a in CONDITIONS) + " |")
    lines += ["", "## Prespecified context contrasts", "", "All effects are percentage points. Bonferroni intervals use a nominal 95% family level across eight within-model contrasts and four model-by-context interactions.", "",
        "| Model | Contrast | Effect | 95% | Simultaneous 99.583% |", "|---|---|---:|---:|---:|"]
    for m, effects in r["effects"].items():
        for name, pair in effects.items():
            a,b = pair["ordinary_95"],pair["simultaneous_99_583"]
            lines.append(f"| {m} | {name} | {100*a['estimate']:+.1f} | [{100*a['low']:+.1f}, {100*a['high']:+.1f}] | [{100*b['low']:+.1f}, {100*b['high']:+.1f}] |")
    for name,pair in r["model_context_interactions"].items():
        a,b=pair["ordinary_95"],pair["simultaneous_99_583"]
        lines.append(f"| small effect minus large effect | {name} | {100*a['estimate']:+.1f} | [{100*a['low']:+.1f}, {100*a['high']:+.1f}] | [{100*b['low']:+.1f}, {100*b['high']:+.1f}] |")
    lines += ["", "## Two-draw policies at $0.01", "", "Conditional on the sampled failed prefix. Direct controls omit producer cost and refer only to this failure population.", "",
              "| Policy | Success | Mean API dollars | Net utility |", "|---|---:|---:|---:|"]
    for name, row in r["policy_summary"]["0.01"].items():
        lines.append(f"| {name} | {100*row['success']:.1f}% | ${row['cost_usd']:.8f} | ${row['net_utility_usd']:.8f} |")
    lines += ["", "The escalation_diagnostic is an additional fixed 9B-fresh then 27B-fresh replay, added after recovery collection began. It does not replace the frozen primary or transfer a newly generated child's code.",
        "", "## Prediction and limitations", "", "| View | Brier | Observed benefit MSE |", "|---|---:|---:|"]
    for v in r["brier"]:
        lines.append(f"| {v} | {r['brier'][v]:.6f} | {r['benefit_mse'][v]:.6f} |")
    lines += ["", f"State-feedback benefit-MSE difference: `{r['state_feedback_benefit_mse_difference']}`.", "",
        f"Initial public false positives: {r['initial_public_false_positives']}; branch false positives: {r['branch_public_false_positives']}; explicit provider errors: {r['explicit_provider_errors']}.", "",
        f"Collection accounting: `{r['collection']}`.", "",
        "This is one benchmark/producer/provider pair and one checkpoint. Cheap structural artifact features do not exhaust semantic artifact value. Task lengths shift across benchmarks. Character-matched distractors are not token-matched; see token receipts in analysis.json. Model pretraining contamination cannot be ruled out. No general multi-step controller or CodeRescue reproduction is established.", "",
        "The former HumanEval+ evaluation is now training data for this replica. Keep its earlier frozen evaluation result separate. Sensitivity rotations, all budgets/actions, noisy-benefit diagnostics and feature shifts are in analysis.json. No secondary test is substituted for the primary.", ""]
    if r["missing_state_utility_bounds"]:
        lines += [f"Missing selected-state worst-case utility bounds: `{r['missing_state_utility_bounds']}`.", ""]
    if r.get("censored_branch_requests"):
        lines += ["## Transport censoring", "",f"Censored solver admissions (never reissued): `{r['censored_branch_requests']}`.","",
                  r.get("recovery_continuation_note") or "Collection stopped under the frozen no-resume rule.",""]
    if "semantic_control" in r:
        s=r["semantic_control"]
        lines += ["## Prespecified outcome-blind semantic control", "",
            "Prompt/code/config were fixed before recovery outcomes, but these forecast responses were collected afterwards. This is secondary and does not replace the physically prospective primary.", "",
            f"Complete matched semantic forecasts: {s['complete_states']}/{s['selected_states']}; malformed forecasts: {s['malformed_forecasts']}.", "",
            "| API view | Brier | Observed benefit MSE | Two-draw success | Mean API dollars |",
            "|---|---:|---:|---:|---:|"]
        for v,x in s["prediction_metrics"].items():
            row=s["policy_summary"]["0.01"][v]
            lines.append(f"| {v} | {x['brier']:.6f} | {x['benefit_mse']:.6f} | {100*row['success']:.1f}% | ${row['cost_usd']:.8f} |")
        lines += ["",f"Full-state minus feedback-only net utility: `{s['state_feedback_utility']}`.","",
            f"Secondary collection accounting: `{s['collection']}`.","",
            "Forecaster fees and advance admission ceilings are included. Missing states/forecasts are not free predictions; any complete-case comparison is descriptive if a selected state is absent.",""]
    return "\n".join(lines)


def analyze_semantic(data,root,*,freeze_path=Path("experiments/mbpp-plus/context-value-transfer/configs/semantic-control-freeze.json")):
    """Secondary forecast audit; the original primary statistic is unchanged."""
    from vao.decisions.context_value import parse_forecast
    from vao.decisions.transfer_forecast import VIEWS as API_VIEWS, messages
    cfg,policy=data["config"],data["policy"]
    manifest=json.loads((root/"manifest.json").read_text())
    if (root/"checksums.json").exists():
        for name,expected in json.loads((root/"checksums.json").read_text()).items():
            require(file_hash(root/name)==expected,"Semantic curated checksum: "+name)
    frozen_path=freeze_path
    frozen=json.loads(frozen_path.read_text())
    require(frozen["target_responses_at_freeze_check"]==0,"Control not fixed before recovery")
    require(manifest["source_manifest_sha256"]==frozen["source_primary_manifest_sha256"],"Primary source changed")
    require(manifest["source_manifest_sha256"]==data["manifest_sha256"],"Forecasts belong to a different primary bank")
    require(manifest["semantic_freeze_sha256"]==file_hash(frozen_path),"Semantic freeze changed")
    require(manifest["source_file_sha256"]==frozen["source_file_sha256"],"Semantic prompt/source changed")
    require(manifest["config"]==cfg and manifest["source_policy_sha256"]==digest(policy),"Semantic prior/config changed")
    require(same(manifest["prior_upper_usd"],data["collection"]["campaign_upper_usd"]),"Semantic budget omits prior charges/reservations")
    call_rows=records(root,"calls")
    calls={r["call"]:r for r in call_rows}
    require(len(calls)==len(call_rows),"Duplicate semantic response identity")
    require(len({r["generation_id"] for r in call_rows})==len(calls),"Duplicate semantic generation identity")
    ledger=records(root,"budget")
    reserved,settled={},{}
    cap=Decimal(str(manifest["maximum_new_budget_usd"]))
    require(0<cap<=Decimal(".08"),"Unapproved semantic allowance")
    for r in ledger:
        c=r["call"]
        if r["event"]=="reserve":
            require(c not in reserved and Decimal(str(r["reserved_usd"]))==reservation(cfg,"small"),"Semantic admission")
            reserved[c]=Decimal(str(r["reserved_usd"]))
        else:
            require(r["event"]=="settle" and c in reserved and c not in settled,"Semantic settlement")
            settled[c]=Decimal(str(r["cost_usd"]))
            require(0<=settled[c]<=reserved[c],"Semantic over-reservation charge")
        require(sum(settled.values())+sum(v for k,v in reserved.items() if k not in settled)<=cap,"Semantic budget exceeded")
    require(set(calls)==set(settled),"Semantic response/receipt census")
    transport=records(root,"transport")
    require(len({r["call"] for r in transport})==len(transport),"Repeated uncertain semantic admission")
    require(set(reserved)-set(settled)=={r["call"] for r in transport},"Unexplained unresolved semantic reservation")
    admitted_cells=[(r["checkpoint_id"],r["view"]) for r in call_rows]
    for r in transport:
        require(r["action"]=="forecast" and r["model_name"]=="small"
                and r["checkpoint_id"] in data["selected"] and r["view"] in API_VIEWS,
                "Unplanned censored semantic request")
        require(r["task_id"]==data["checkpoints"][r["checkpoint_id"]]["task_id"],"Censored semantic task identity")
        admitted_cells.append((r["checkpoint_id"],r["view"]))
    require(len(set(admitted_cells))==len(admitted_cells),"Repeated semantic state/view admission")
    prediction_rows=records(root,"predictions")
    by_call={r["call"]:r for r in prediction_rows}
    require(len(calls)==len(prediction_rows)==len(by_call),"Missing/repeated semantic observation")
    predictions={}
    for c,r in calls.items():
        cp=data["checkpoints"][r["checkpoint_id"]]
        require(r["checkpoint_id"] in data["selected"] and r["view"] in API_VIEWS,"Unplanned semantic state/view")
        require(r["task_id"]==cp["task_id"] and r["action"]=="forecast","Semantic identity")
        require(r["messages"]==messages(data["prompts"][cp["task_id"]],cp,policy,cfg,r["view"]),"Semantic outcome leak/projection drift")
        require(r["model"]==r["returned_model"]==cfg["models"]["small"]["id"] and r["provider"].lower()=="siliconflow","Semantic model/provider drift")
        require(not (r["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens",0) and r.get("seed_sent") is None,"Semantic sampling drift")
        require(Decimal(str(r["usage"]["cost"]))==settled[c],"Semantic receipt mismatch")
        p,valid=parse_forecast(r,cfg)
        saved=by_call[c]
        require(all(saved[k]==r[k] for k in ("task_id","checkpoint_id","view")),"Semantic prediction identity changed")
        require(saved["probabilities"]==p and saved["valid"]==valid and Decimal(str(saved["cost_usd"]))==settled[c],"Semantic parse/cost mismatch")
        key=(r["checkpoint_id"],r["view"])
        require(key not in predictions,"Duplicate semantic state/view")
        predictions[key]=saved
    ids=[id_ for id_ in data["complete"] if all((id_,v) in predictions for v in API_VIEWS)]
    require(len(ids)>1,"Too few complete matched semantic states")
    grouped={id_:[r for r in data["branches"] if r["checkpoint_id"]==id_] for id_ in ids}
    losses={v:[] for v in API_VIEWS}; benefits={v:[] for v in API_VIEWS}
    for id_ in ids:
        rows=grouped[id_]
        for v in API_VIEWS:
            p=predictions[(id_,v)]["probabilities"]
            losses[v].append(np.mean([(p[r["model_name"]+"."+r["arm"]]-r["passed"])**2 for r in rows if r["arm"] in ARMS]))
            errors=[]
            for m in cfg["target_models"]:
                for arm in ("feedback","fresh"):
                    delta=np.mean([r["passed"] for r in rows if r["model_name"]==m and r["arm"]=="artifact_feedback"])-np.mean([r["passed"] for r in rows if r["model_name"]==m and r["arm"]==arm])
                    errors.append((p[m+".artifact_feedback"]-p[m+"."+arm]-delta)**2)
            benefits[v].append(np.mean(errors))
    rollouts=[]; summaries={}
    for budget in cfg["task_budgets_usd"]:
        summaries[str(budget)]={}
        for view in API_VIEWS:
            for id_ in ids:
                cp=data["checkpoints"][id_]
                forecast=predictions[(id_,view)]
                prefix=Decimal(str(cp["prefix_cost_usd"]))
                action=None
                if prefix+reservation(cfg,"small")<=Decimal(str(budget)):
                    prefix+=Decimal(str(forecast["cost_usd"]))
                    action=choose(policy,forecast["probabilities"],cfg,budget,float(prefix))
                outcome=replay(grouped[id_],action,float(prefix),cfg,budget)
                rollouts.append({"checkpoint_id":id_,"task_id":cp["task_id"],"policy":"api_"+view,"budget_usd":budget,"rotation":0,
                    "selected_action":action,**outcome,"net_utility_usd":.01*outcome["passed"]-outcome["cost_usd"]})
            rows=[r for r in rollouts if r["policy"]=="api_"+view and r["budget_usd"]==budget]
            summaries[str(budget)][view]={"success":float(np.mean([r["passed"] for r in rows])),"cost_usd":float(np.mean([r["cost_usd"] for r in rows])),
                "net_utility_usd":float(np.mean([r["net_utility_usd"] for r in rows]))}
    a=[r for r in rollouts if r["policy"]=="api_state" and r["budget_usd"]==.01]
    b=[r for r in rollouts if r["policy"]=="api_feedback_only" and r["budget_usd"]==.01]
    comparisons={}
    for name in ("feedback_only","task_only","best_static"):
        if name=="best_static":
            control=[replay(grouped[id_],policy["development_replay_fixed"]["0.01"],data["checkpoints"][id_]["prefix_cost_usd"],cfg,.01) for id_ in ids]
            for r in control:r["net_utility_usd"]=.01*r["passed"]-r["cost_usd"]
        else:
            control=[r for r in rollouts if r["policy"]=="api_"+name and r["budget_usd"]==.01]
        comparisons[name]=interval([x["net_utility_usd"]-y["net_utility_usd"] for x,y in zip(a,control)])
    upper=Decimal(str(manifest["prior_upper_usd"]))+sum(settled.values())+sum(v for k,v in reserved.items() if k not in settled)
    require(upper<=Decimal(str(cfg["campaign_ceiling_usd"])),"Semantic campaign overspend")
    report={"selected_states":len(data["selected"]),"complete_states":len(ids),"malformed_forecasts":sum(not r["valid"] for r in prediction_rows),
        "prediction_metrics":{v:{"brier":float(np.mean(losses[v])),"benefit_mse":float(np.mean(benefits[v]))} for v in API_VIEWS},
        "state_feedback_brier_difference":interval(np.array(losses["state"])-losses["feedback_only"]),
        "state_feedback_benefit_mse_difference":interval(np.array(benefits["state"])-benefits["feedback_only"]),
        "state_feedback_utility":comparisons["feedback_only"],"state_utility_comparisons":comparisons,"policy_summary":summaries,
        "collection":{"responses":len(calls),"known_cost_usd":float(sum(settled.values())),
            "unresolved_reservations_usd":float(sum(v for k,v in reserved.items() if k not in settled)),"campaign_upper_usd":float(upper)}}
    return report,rollouts


def plot(r, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    # Seven-inch width preserves readable labels when included at full paper width.
    fig,ax = plt.subplots(2,1,figsize=(7,6.8),layout="constrained")
    labels, points, lows, highs = [],[],[],[]
    for m in r["effects"]:
        for name,pair in r["effects"][m].items():
            a = pair["simultaneous_99_583"]
            labels.append({"small":"9B","large":"27B"}[m]+" / "+name.replace("artifact_feedback","both").replace("artifact","code"))
            points.append(100*a["estimate"]); lows.append(100*(a["estimate"]-a["low"])); highs.append(100*(a["high"]-a["estimate"]))
    y = np.arange(len(labels))
    ax[0].errorbar(points,y,xerr=[lows,highs],fmt="o",capsize=3)
    ax[0].axvline(0,color="gray",lw=1); ax[0].set_yticks(y,labels); ax[0].invert_yaxis()
    ax[0].set_xlabel("Full-suite success difference (percentage points)")
    ax[0].set_title("A. Context effects: 99.583% intervals (12-comparison family)",loc="left")
    names = ["best_static", "feedback", "state", "state_model_only"]
    policy_labels = {"best_static":"Source-selected static", "feedback":"Feedback-only selector",
                     "state":"State selector", "state_model_only":"Model-only selector"}
    for name in names:
        row=r["policy_summary"]["0.01"][name]
        ax[1].scatter(row["cost_usd"]*1000,row["success"]*100,label=policy_labels[name],s=45)
    ax[1].set_xlabel("Mean API cost per failed task (USD × 1,000)")
    ax[1].set_ylabel("Recovery success (%)")
    ax[1].set_title("B. Two-draw replay at $0.01; producer charged",loc="left")
    ax[1].legend(fontsize=8,loc="best")
    fig.suptitle(f"MBPP+ replication: {r['complete_states']} failed tasks")
    fig.savefig(path,dpi=180); fig.savefig(path.with_suffix(".pdf")); plt.close(fig)

    # Primary decision comparison is displayed directly, rather than inferred
    # from an unpaired cost/success scatter. Other comparators are secondary.
    fig,ax = plt.subplots(figsize=(3.35,3.0),layout="constrained")
    controls = ["feedback", "best_static", "state_model_only", "task", "global", "escalation_diagnostic"]
    labels = ["Feedback (primary)", "Static (source)", "Model only", "Task only", "Global prior", "Escalation*"]
    for i,name in enumerate(controls):
        ci=r["policy_comparisons"]["0"][name]["net_utility_usd"]
        ax.errorbar(1000*ci["estimate"],i,
                    xerr=[[1000*(ci["estimate"]-ci["low"])],[1000*(ci["high"]-ci["estimate"])]],
                    fmt="o",capsize=3,color="C0" if i==0 else "0.45")
    ax.axvline(0,color="0.65",lw=1); ax.set_yticks(range(len(controls)),labels)
    ax.invert_yaxis(); ax.set_xlabel("State minus control utility\n(USD × 1,000/task)")
    ax.set_title("Paired utility differences\n95% task-bootstrap intervals",fontsize=9)
    fig.savefig(path.with_name("policy-utility.png"),dpi=180)
    fig.savefig(path.with_name("policy-utility.pdf")); plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--forecasts",type=Path)
    parser.add_argument("--expected-analysis",type=Path,
                        help="Require the recomputed report to match a saved analysis, allowing only floating-point roundoff.")
    args=parser.parse_args()
    data=audit(args.input)
    report,rollouts=analyze(data)
    if args.forecasts:
        report["semantic_control"],extra=analyze_semantic(data,args.forecasts)
        rollouts+=extra
    if args.expected_analysis:
        require(same(report,json.loads(args.expected_analysis.read_text())),
                "Recomputed report differs from the saved analysis")
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/"analysis.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    (args.output/"rollouts.jsonl").write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rollouts))
    (args.output/"report.md").write_text(markdown(report))
    plot(report,args.output/"replication.png")
    print(json.dumps({"status":report["status"],"primary":report["primary"],"collection":report["collection"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
