"""Plan matched repair collection; live mode requires a funded source freeze.

The default is offline planning. Scripted demonstrations never provide model
evidence. Existing output directories and admitted calls cannot be resumed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import sys
import subprocess
import time

from .environment import REPAIR_SYSTEM, RepairRun, RepairTask, audit_run, canonical, identity
from .pool import read_pool
from .records import append, rows, save
from .provider import OpenRouterTransport, ProviderStopped, Settings, dollars
from .verifier import RepairVerifier


ACTIONS = ("continue", "restart")
DEFAULT_POOL = Path("experiments/python-repair/checkpoint-environment/development")
DEFAULT_CONFIG = Path("experiments/python-repair/checkpoint-environment/PILOT-DRAFT.json")


@dataclass(frozen=True)
class Design:
    """Development sampling plan; no numeric field here authorizes API spending."""

    prefix_replicates: int = 2
    prefix_attempts: int = 3
    draws_per_action: int = 2
    seed: int = 43117

    def __post_init__(self):
        for name in ("prefix_replicates", "prefix_attempts", "draws_per_action", "seed"):
            if type(getattr(self, name)) is not int:
                raise ValueError("Design requires integer values")
        if not (1 <= self.prefix_replicates <= 10 and 1 <= self.prefix_attempts <= 10
                and 2 <= self.draws_per_action <= 10 and self.seed >= 0):
            raise ValueError("Design outside development bounds")

    def maximum_calls(self, tasks: int) -> int:
        return tasks * self.prefix_replicates * self.prefix_attempts * (1 + 2 * self.draws_per_action)


def fingerprint(tasks: list[RepairTask], design: Design) -> dict:
    """Pin task contents and the code used by collection and isolation."""
    from vao.decisions import verification
    paths = list(Path(__file__).parent.glob("*.py")) + [Path(verification.__file__)]
    return {"tasks": [task.task_hash for task in tasks], "design": asdict(design),
            "python": sys.version, "platform": platform.platform(),
            "sources": {str(p.relative_to(Path(__file__).parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(paths)}}


def schedule_for(tasks, design, config=None):
    schedule = [(i, r) for r in range(design.prefix_replicates) for i in range(len(tasks))]
    random.Random(design.seed).shuffle(schedule)
    if config and config.get("continuation"):
        allowed = config["continuation"]["allowed_trajectories"]
        if not allowed or len(allowed) != len(set(allowed)):
            raise ValueError("Continuation requires distinct unstarted trajectories")
        schedule = [(i, r) for i, r in schedule if f"task-{i:03d}-rep-{r:02d}" in allowed]
        if len(schedule) != len(allowed):
            raise ValueError("Continuation includes an undeclared trajectory")
    return schedule


def check_continuation(config, tasks, design) -> Decimal:
    """Validate a proposed manual exception; never retry an admitted trajectory."""
    carried = config.get("continuation")
    if not carried:
        return Decimal(0)
    parent = Path(carried["parent_run"])
    manifest = json.loads((parent / "manifest.json").read_text())
    original = manifest["freeze"]
    checked = audit(parent)
    if (checked["sealed"] or not (parent / "interruption.json").exists()
            or manifest["mode"] != "model_pilot" or original["config"].get("continuation")
            or original["freeze_id"] != carried["parent_freeze_id"]
            or original["provider_settings"] != config["provider_settings"]
            or original["provenance"]["tasks"] != [t.task_hash for t in tasks]
            or original["provenance"]["design"] != asdict(design)
            or file_hashes(parent) != carried["parent_hashes"]):
        raise ValueError("Continuation parent is changed, unsupported or not the original interrupted pilot")
    started = sorted(p.name for p in (parent / "trajectories").glob("*"))
    expected = [f"task-{i:03d}-rep-{r:02d}" for i, r in schedule_for(tasks, design)
                if f"task-{i:03d}-rep-{r:02d}" not in started]
    if carried["allowed_trajectories"] != expected or carried["omitted_started_trajectories"] != started:
        raise ValueError("Only original, entirely unstarted trajectories may continue")
    for event in rows(parent / "ledger.jsonl"):
        if event["event"] == "reserve":
            request = json.loads((parent / "requests" / (event["attempt_id"] + ".json")).read_text())
            if request["metadata"]["trajectory"] in expected:
                raise ValueError("Continuation overlaps an admitted attempt")
    retained = dollars(checked["conservative_committed_usd"])
    ceiling = dollars(carried["cumulative_limit_usd"])
    if (retained != dollars(carried["retained_committed_usd"])
            or ceiling != dollars(manifest["limit_usd"])
            or dollars(config["monetary_authorization_usd"]) + retained != ceiling):
        raise ValueError("Continuation fails cumulative reservation accounting")
    return retained


class ScriptedTransport:
    """Offline fake with a real reservation journal and synthetic dollar amounts."""

    mode = "scripted_pilot"

    def __init__(self, output: Path, responder, *, limit="1", reserve="0.0001", cost="0.00005"):
        self.output, self.responder = output, responder
        self.limit, self.reserve, self.cost = map(Decimal, (limit, reserve, cost))
        if not all(n.is_finite() for n in (self.limit, self.reserve, self.cost)) or not (
            self.limit > 0 and self.reserve > 0 and 0 <= self.cost <= self.reserve
        ):
            raise ValueError("Invalid scripted accounting")
        self.spent, self.pending = Decimal(0), {}
        self.seen = set()

    def available(self, calls=1) -> bool:
        return not self.pending and self.spent + calls * self.reserve <= self.limit

    def complete(self, request: dict, metadata: dict) -> dict:
        attempt = metadata["attempt_id"]
        if attempt in self.seen or not self.available():
            raise ValueError("Duplicate attempt or unavailable budget")
        self.seen.add(attempt)
        self.pending[attempt] = self.reserve
        append(self.output / "ledger.jsonl", {"event": "reserve", "attempt_id": attempt,
               "usd": str(self.reserve), "currency": "simulated_USD"})
        # A responder exception leaves the reserve and request intact, with no retry.
        value = self.responder(request, metadata)
        record = {"attempt_id": attempt, "model": "scripted-fixture", "provider": "offline",
                  "content": value if isinstance(value, str) else canonical(value),
                  "finish_reason": "stop", "cost_usd": str(self.cost), "mode": self.mode}
        save(self.output / "receipts" / (attempt + ".json"), record)
        append(self.output / "ledger.jsonl", {"event": "settle", "attempt_id": attempt,
               "usd": str(self.cost), "currency": "simulated_USD"})
        self.pending.pop(attempt)
        self.spent += self.cost
        return record


def evaluate_response(run: RepairRun, call: dict) -> dict:
    """Preserve malformed outputs as paid failures; do not fabricate a patch."""
    try:
        files = json.loads(call["content"])
        if call["finish_reason"] != "stop":
            raise ValueError("Incomplete response")
        run.task.validate_artifact(files)
    except (ValueError, TypeError, KeyError, RecursionError):
        return {"status": "format_error", "artifact": None, "public": None,
                "evaluator": None, "full_pass": False}
    artifact = run.snapshot(files)
    public = run.evaluate(artifact, "public")
    evaluator = run.evaluate(artifact, "evaluator")
    return {"status": "evaluated", "artifact": artifact, "public": public,
            "evaluator": evaluator,
            "full_pass": run.get(public)["result"]["passed"] and run.get(evaluator)["result"]["passed"]}


def public_choice(candidates: list[dict]) -> str | None:
    """Choose only from public scores, with a supplied outcome-independent order."""
    if not candidates or any(c.get("missing") for c in candidates):
        return None
    # All candidates for a checkpoint share the public suite size. None is a
    # malformed response and ranks below any executable (even zero-pass) artifact.
    return max(candidates, key=lambda c: c["public_passed_cases"] if c["public_passed_cases"] is not None else -1)["attempt_id"]


def collect(tasks: list[RepairTask], design: Design, output: Path, verifier, factory, *, freeze=None) -> dict:
    """Collect a development bank under the supplied, independently frozen cap."""
    if not tasks or len({t.public["task_id"] for t in tasks}) != len(tasks):
        raise ValueError("Tasks must be nonempty and unique")
    carried = check_continuation(freeze["config"], tasks, design) if freeze else Decimal(0)
    schedule = schedule_for(tasks, design, freeze["config"] if freeze else None)
    output.mkdir(parents=True, exist_ok=False)
    (output / "receipts").mkdir()
    (output / "requests").mkdir()
    transport = factory(output)
    live = freeze is not None
    if live:
        if (not isinstance(transport, OpenRouterTransport) or transport.mode != "model_pilot"
                or freeze["provenance"] != fingerprint(tasks, design)
                or freeze["provider_settings"] != asdict(transport.settings)
                or dollars(freeze["authorized_limit_usd"]) != transport.limit):
            raise ValueError("Live adapter does not match the funded freeze")
    elif type(transport) is not ScriptedTransport or transport.mode != "scripted_pilot":
        raise ValueError("Without a freeze only the offline scripted adapter is allowed")
    manifest = {"mode": transport.mode, "model_results": live,
                "provenance": fingerprint(tasks, design), "resume_allowed": False,
                "limit_usd": str(transport.limit), "reservation_usd": str(transport.reserve),
                "checkpoint_allowance_usd": str(2 * transport.reserve),
                "currency": "USD" if live else "simulated_USD",
                "maximum_calls": len(schedule) * design.prefix_attempts * (1 + 2 * design.draws_per_action),
                "carried_committed_usd": str(carried)}
    if live:
        manifest.update({"freeze": freeze, "provider_settings": asdict(transport.settings)})
    save(output / "manifest.json", manifest)
    observations, trajectories = [], []
    save(output / "schedule.json", {"trajectories": schedule})
    try:
        if live:
            transport.preflight()
        for index, replicate in schedule:
            task = tasks[index]
            trajectory_id = f"task-{index:03d}-rep-{replicate:02d}"
            run = RepairRun(output / "trajectories" / trajectory_id, task, verifier, mode=transport.mode)
            initial_ev = run.evaluate(run.initial, "public")
            cp = run.checkpoint(run.initial, initial_ev)
            prefix_cost = Decimal(0)
            reason = "maximum_prefix_attempts"
            prefix_ids = []

            def generate(checkpoint, action, meta):
                meta = {"trajectory": trajectory_id, "task_hash": task.task_hash, **meta}
                meta["attempt_id"] = identity(meta)
                branch = run.fork(checkpoint, action, manifest["checkpoint_allowance_usd"])
                request = run.request(branch)
                save(output / "requests" / (meta["attempt_id"] + ".json"),
                     {"metadata": meta, "checkpoint": checkpoint, "branch": branch, "request": request})
                receipt = transport.complete(request, meta)
                result = evaluate_response(run, receipt)
                score = run.get(result["public"])["result"]["passed_cases"] if result["public"] else None
                row = {**meta, **result, "checkpoint_before": checkpoint, "branch": branch,
                       "public_passed_cases": score, "cost_usd": receipt["cost_usd"],
                       "prefix_cost_usd": str(prefix_cost), "prefix_attempt_ids": list(prefix_ids)}
                append(output / "observations.jsonl", row)
                observations.append(row)
                return row

            for depth in range(1, design.prefix_attempts + 1):
                if run.get(cp)["feedback"]["passed"]:
                    reason = "public_pass"
                    break
                if not transport.available():
                    reason = "collection_budget"
                    break
                prefix = generate(cp, "continue", {"phase": "prefix", "depth": depth})
                prefix_cost += Decimal(prefix["cost_usd"])
                prefix_ids.append(prefix["attempt_id"])
                if prefix["status"] == "format_error":
                    reason = "prefix_format_error"
                    break
                cp = run.checkpoint(prefix["artifact"], prefix["public"], cp)
                if run.get(cp)["feedback"]["passed"]:
                    reason = "public_pass"
                    break
                group = identity({"trajectory": trajectory_id, "checkpoint": cp, "depth": depth})
                branch_schedule = []
                for draw in range(design.draws_per_action):
                    actions = list(ACTIONS)
                    # Counterbalance call order without using any outcome.
                    random.Random(f"{design.seed}:{trajectory_id}:{depth}:{draw}").shuffle(actions)
                    branch_schedule.extend({"action": a, "draw": draw} for a in actions)
                planned = {"group": group, "trajectory": trajectory_id, "checkpoint": cp,
                           "depth": depth, "branches": branch_schedule,
                           "prefix_attempt_ids": list(prefix_ids), "prefix_cost_usd": str(prefix_cost)}
                append(output / "groups.jsonl", planned)
                # Avoid beginning a knowingly unaffordable matched set. An
                # uncertain call still aborts collection and preserves reserves.
                if not transport.available(len(branch_schedule)):
                    append(output / "missing.jsonl", {"group": group, "reason": "collection_budget",
                                                       "unattempted": branch_schedule})
                    reason = "collection_budget"
                    break
                for spec in branch_schedule:
                    generate(cp, spec["action"], {"phase": "branch", "group": group,
                             "depth": depth, **spec})
                # cp is the original prefix checkpoint, never a branch result.
            trajectory = {"id": trajectory_id, "task_hash": task.task_hash, "replicate": replicate,
                          "reason": reason, "prefix_attempt_ids": prefix_ids,
                          "prefix_cost_usd": str(prefix_cost), "audit": audit_run(run.root)}
            save(run.root / "completion.json", {"audit": trajectory["audit"], "mode": transport.mode})
            append(output / "trajectories.jsonl", trajectory)
            trajectories.append(trajectory)
        if fingerprint(tasks, design) != manifest["provenance"]:
            raise ValueError("Source or task changed during collection")
    except Exception as exc:
        save(output / "interruption.json", {"exception_type": type(exc).__name__,
             "resume_allowed": False, "pending": {k: str(v) for k, v in transport.pending.items()},
             "settled_usd": str(transport.spent),
             "carried_committed_usd": str(carried),
             "conservative_committed_usd": str(carried + (transport.conservative_committed_usd if live else
                                              transport.spent + sum(transport.pending.values())))})
        raise
    report = {"mode": transport.mode, "model_results": live, "api_calls": len(transport.seen) if live else 0,
              "api_spend_usd": str(transport.spent) if live else "0",
              "carried_committed_usd": str(carried), "cumulative_committed_usd": str(carried + transport.spent),
              "observations": len(observations), "trajectories": len(trajectories),
              "simulated_spend_usd": "0" if live else str(transport.spent),
              "missing_groups": len(rows(output / "missing.jsonl")),
              "limitation": ("Inspected development bugs; not a held-out selector evaluation." if live else
                             "Handwritten responses and simulated prices; no model efficacy evidence.")}
    save(output / "pilot-completion.json", {**report, "file_hashes": file_hashes(output)})
    audit(output)
    return report


def file_hashes(output: Path) -> dict:
    return {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*")) if p.is_file() and p.name != "pilot-completion.json"}


def audit(output: Path) -> dict:
    """Audit saved requests, response identities, matched inputs and ledger offline."""
    manifest = json.loads((output / "manifest.json").read_text())
    live = manifest["mode"] == "model_pilot"
    currency = "USD" if live else "simulated_USD"
    if manifest["mode"] not in {"model_pilot", "scripted_pilot"} or manifest["currency"] != currency or manifest["model_results"] != live:
        raise ValueError("Pilot mode/currency mismatch")
    settings = Settings(**manifest["provider_settings"]) if live else None
    ledger, pending, settled = rows(output / "ledger.jsonl"), {}, {}
    used = Decimal(0)
    for event in ledger:
        key, amount = event["attempt_id"], Decimal(event["usd"])
        if not amount.is_finite() or amount < 0 or event["currency"] != currency:
            raise ValueError("Invalid ledger amount")
        if event["event"] == "reserve":
            if key in pending or key in settled or amount <= 0:
                raise ValueError("Duplicate or invalid admission")
            if used + sum(pending.values()) + amount > Decimal(manifest["limit_usd"]):
                raise ValueError("Admission exceeds campaign cap")
            pending[key] = amount
        elif event["event"] == "settle":
            if key not in pending or amount > pending[key]:
                raise ValueError("Settlement without valid reserve")
            pending.pop(key)
            settled[key] = amount
            used += amount
        else:
            raise ValueError("Unknown ledger event")
    observations = rows(output / "observations.jsonl")
    seen, groups, prior = set(), {}, {}
    for row in observations:
        key = row["attempt_id"]
        if key in seen or key not in settled:
            raise ValueError("Duplicate or unsettled observation")
        seen.add(key)
        receipt = json.loads((output / "receipts" / (key + ".json")).read_text())
        request = json.loads((output / "requests" / (key + ".json")).read_text())
        if receipt["attempt_id"] != key or Decimal(receipt["cost_usd"]) != settled[key] or Decimal(row["cost_usd"]) != settled[key]:
            raise ValueError("Receipt/ledger mismatch")
        metadata = dict(request["metadata"])
        if metadata.pop("attempt_id") != key or identity(metadata) != key:
            raise ValueError("Request identity mismatch")
        if any(row.get(k) != v for k, v in metadata.items()):
            raise ValueError("Observation metadata differs from admitted request")
        if receipt["mode"] != manifest["mode"] or request["request"]["mode"] != manifest["mode"]:
            raise ValueError("Request/receipt mode mismatch")
        if live:
            provider_body = json.loads((output / "requests" / (key + ".provider.json")).read_text())
            raw = json.loads((output / "receipts" / (key + ".raw.json")).read_text())
            if provider_body != settings.body(request["request"], request["metadata"]):
                raise ValueError("Provider payload differs from frozen solver projection")
            if (raw["model"] != settings.model or raw["provider"] != settings.provider_name
                    or receipt["generation_id"] != raw["id"] or receipt["usage"] != raw["usage"]
                    or dollars(raw["usage"]["cost"]) != settled[key]
                    or receipt["content"] != raw["choices"][0].get("message", {}).get("content")
                    or receipt["finish_reason"] != raw["choices"][0].get("finish_reason")):
                raise ValueError("Provider receipt projection mismatch")
        run_root = output / "trajectories" / row["trajectory"]
        def obj(ref):
            return json.loads((run_root / "objects" / (ref + ".json")).read_text())
        branch = obj(row["branch"])
        cp = obj(branch["checkpoint"])
        event = json.loads((run_root / "events" / "000000.json").read_text())
        task_obj, initial = [obj(ref) for ref in event["objects"]]
        if request["branch"] != row["branch"] or request["checkpoint"] != row["checkpoint_before"] or branch["checkpoint"] != row["checkpoint_before"]:
            raise ValueError("Request branch/checkpoint mismatch")
        if (len(request["request"]["messages"]) != 2 or request["request"]["messages"][1].get("role") != "user"
                or request["request"]["messages"][0] != {"role": "system", "content": REPAIR_SYSTEM}):
            raise ValueError("Unexpected system instructions")
        payload = json.loads(request["request"]["messages"][1]["content"])
        if set(payload) != {"instruction", "entrypoint", "public_cases", "latest_feedback", "files"}:
            raise ValueError("Unexpected solver information")
        if payload["latest_feedback"] != {k: cp["feedback"][k] for k in ("passed", "passed_cases", "total_cases", "cases")}:
            raise ValueError("Feedback projection mismatch")
        if payload["files"] != obj(branch["starting_artifact"])["files"]:
            raise ValueError("Artifact projection mismatch")
        if any(payload[k] != task_obj["public"][k] for k in ("instruction", "entrypoint", "public_cases")):
            raise ValueError("Task projection mismatch")
        action = row.get("action", "continue")
        if branch["action"] != action or action not in ACTIONS:
            raise ValueError("Action mismatch")
        expected_files = initial["files"] if action == "restart" else obj(cp["artifact"])["files"]
        if payload["files"] != expected_files:
            raise ValueError("Incorrect action starting state")
        prefix = row["prefix_attempt_ids"]
        if any(p not in prior or prior[p]["phase"] != "prefix" or prior[p]["trajectory"] != row["trajectory"] for p in prefix):
            raise ValueError("Branch outcome or future data used as prefix")
        if len(prefix) != row["depth"] - (row["phase"] == "prefix"):
            raise ValueError("Prefix depth mismatch")
        if sum((Decimal(prior[p]["cost_usd"]) for p in prefix), Decimal(0)) != Decimal(row["prefix_cost_usd"]):
            raise ValueError("Prefix accounting mismatch")
        if prefix and (cp["artifact"] != prior[prefix[-1]]["artifact"] or cp["evaluation"] != prior[prefix[-1]]["public"]):
            raise ValueError("Prefix continuation uses another branch")
        if not prefix and obj(cp["artifact"])["files"] != initial["files"]:
            raise ValueError("Prefix does not start at the original artifact")
        if row["artifact"]:
            pub, ev = obj(row["public"]), obj(row["evaluator"])
            if pub["artifact"] != row["artifact"] or ev["artifact"] != row["artifact"] or pub["channel"] != "public" or ev["channel"] != "evaluator":
                raise ValueError("Evaluation attachment mismatch")
            if row["public_passed_cases"] != pub["result"]["passed_cases"] or row["full_pass"] != (pub["result"]["passed"] and ev["result"]["passed"]):
                raise ValueError("Outcome differs from saved verification")
        elif row["status"] != "format_error" or row["full_pass"] or row["public_passed_cases"] is not None:
            raise ValueError("Malformed output mislabeled")
        prior[key] = row
        if row["phase"] == "branch":
            groups.setdefault(row["group"], []).append(request["request"])
    for requests in groups.values():
        normalized = []
        for request in requests:
            payload = json.loads(request["messages"][1]["content"])
            payload.pop("files")
            normalized.append({**request, "messages": [request["messages"][0], {"role": "user", "content": canonical(payload)}]})
        if any(r != normalized[0] for r in normalized):
            raise ValueError("Unmatched branch requests")
    for path in sorted((output / "trajectories").glob("*")):
        audit_run(path)
    completion = output / "pilot-completion.json"
    if completion.exists():
        saved = json.loads(completion.read_text())
        if pending or set(settled) != seen or saved["file_hashes"] != file_hashes(output):
            raise ValueError("Incomplete or modified sealed pilot")
        if saved["observations"] != len(seen) or saved["api_calls"] != (len(settled) if live else 0):
            raise ValueError("Completion counts mismatch")
    carried = dollars(manifest.get("carried_committed_usd", "0"))
    if live and carried:
        link = manifest["freeze"]["config"]["continuation"]
        parent = Path(link["parent_run"])
        if file_hashes(parent) != link["parent_hashes"] or dollars(audit(parent)["conservative_committed_usd"]) != carried:
            raise ValueError("Continuation parent or retained accounting changed")
    committed = used + carried
    for key, reserved in pending.items():
        known = Decimal(0)
        raw = output / "receipts" / (key + ".raw.json")
        if live and raw.exists():
            try:
                known = dollars(json.loads(raw.read_text())["usage"]["cost"])
            except (KeyError, TypeError, ValueError, ProviderStopped):
                pass
        committed += max(reserved, known)
    return {"verified_observations": len(seen), "pending": {k: str(v) for k, v in pending.items()},
            "settled_usd": str(used), "conservative_committed_usd": str(committed),
            "carried_committed_usd": str(carried),
            "cap_exceeded": committed > Decimal(manifest["limit_usd"]) + carried,
            "sealed": completion.exists(), "api_calls": len(settled) + len(pending) if live else 0}


def comparisons(output: Path) -> list[dict]:
    """Return costed fixed/two-candidate rows, never claim scripted policy gains."""
    audit(output)
    observations = rows(output / "observations.jsonl")
    manifest = json.loads((output / "manifest.json").read_text())
    result = []
    by_id = {row["attempt_id"]: row for row in observations}
    for group in rows(output / "groups.jsonl"):
        candidates = {(r["action"], r["draw"]): r for r in observations
                      if r.get("group") == group["group"]}
        mixed = [("continue", 0), ("restart", 0)]
        if int(group["group"], 16) % 2:
            mixed.reverse()  # A frozen tie order independent of public/private outcomes.
        policies = {"continue_one": [("continue", 0)], "restart_one": [("restart", 0)],
                    "continue_two_public_select": [("continue", 0), ("continue", 1)],
                    "restart_two_public_select": [("restart", 0), ("restart", 1)],
                    "mixed_two_public_select": mixed}
        for policy, keys in policies.items():
            available = [candidates[k] for k in keys if k in candidates]
            complete = len(available) == len(keys)
            selection_inputs = [{"attempt_id": c["attempt_id"],
                                 "public_passed_cases": c["public_passed_cases"]} for c in available]
            start = time.perf_counter()
            selected = public_choice(selection_inputs) if complete else None
            selection_seconds = time.perf_counter() - start
            winner = next((c for c in available if c["attempt_id"] == selected), None)
            # The unselected candidate is still paid for. All policies pay the
            # same sunk prefix once, not once per candidate or physical branch.
            cost = Decimal(group["prefix_cost_usd"]) + sum((Decimal(c["cost_usd"]) for c in available), Decimal(0))
            prefix = [by_id[key] for key in group["prefix_attempt_ids"]]
            run = output / "trajectories" / group["trajectory"]
            def obj(ref):
                return json.loads((run / "objects" / (ref + ".json")).read_text())
            initial_cp = obj(prefix[0]["checkpoint_before"])
            verifier_seconds = {channel: sum(obj(row[channel])["result"]["verifier_seconds"]
                                for row in prefix + available if row[channel]) for channel in ("public", "evaluator")}
            verifier_seconds["public"] += obj(initial_cp["evaluation"])["result"]["verifier_seconds"]
            result.append({"group": group["group"], "trajectory": group["trajectory"],
                           "policy": policy, "status": "complete" if complete else "missing",
                           "selected_attempt": selected, "full_pass": winner["full_pass"] if winner else None,
                           "cost_usd": str(cost) if complete else None,
                           "known_cost_usd": str(cost), "required_candidates": len(keys),
                           "known_public_verifier_seconds": verifier_seconds["public"],
                           "known_evaluator_verifier_seconds": verifier_seconds["evaluator"],
                           "replay_selection_seconds": selection_seconds,
                           "checkpoint_allowance_usd": manifest["checkpoint_allowance_usd"],
                           "candidate_attempts": [c["attempt_id"] for c in available],
                           "currency": manifest["currency"], "model_results": manifest["model_results"]})
    return result


def demo(bundle: Path, output: Path) -> dict:
    task = RepairTask.load(bundle)
    if task.public["provenance"]["kind"] != "synthetic_engineering_fixture":
        raise ValueError("Scripted demo requires a labeled synthetic fixture")
    scripted = list(json.loads((bundle / "scripted-attempts.json").read_text()).values())
    reference = json.loads((bundle / "reference.json").read_text())
    def responder(request, meta):
        if meta["phase"] == "prefix":
            return scripted[meta["depth"] - 1]
        return reference if meta["draw"] == 1 else scripted[0]
    verifier = RepairVerifier()
    verifier.preflight()
    return collect([task], Design(1, 2, 2), output, verifier,
                   lambda out: ScriptedTransport(out, responder))


def source_commit() -> str:
    """Require a committed, clean checkout before freezing or sending calls."""
    repo = Path(__file__).resolve().parents[3]
    state = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"],
                           cwd=repo, capture_output=True, text=True, check=True).stdout
    if state:
        raise ValueError("Commit and review source changes before a live freeze")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()


def funded_freeze(config: dict, tasks: list[RepairTask], output: Path) -> dict:
    """Save a funded config without sending any request. Never infer permission."""
    if (config.get("live_calls_enabled") is not True or config.get("status") != "authorized_development_pilot"
            or not isinstance(config.get("authorization_reference"), str) or not config["authorization_reference"].strip()
            or not re.fullmatch(r"[a-z][a-z0-9-]{5,100}", config.get("campaign_id", ""))):
        raise ValueError("Explicit new authorization and a funded pilot config are required")
    design, settings = Design(**config["design"]), Settings(**config["provider_settings"])
    limit = dollars(config["monetary_authorization_usd"])
    check_continuation(config, tasks, design)
    maximum = settings.reserve * len(schedule_for(tasks, design, config)) * design.prefix_attempts * (1 + 2 * design.draws_per_action)
    if not maximum <= limit <= 5:
        raise ValueError("Pilot cap must cover the full conservative design and be at most 5 USD")
    record = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": source_commit(), "provenance": fingerprint(tasks, design),
              "provider_settings": asdict(settings), "authorized_limit_usd": str(limit),
              "authorization_reference": config["authorization_reference"],
              "maximum_reserved_usd": str(maximum), "config": config}
    record["freeze_id"] = identity(record)
    save(output, record)
    return record


def validate_freeze(freeze: dict, tasks: list[RepairTask]) -> Design:
    content = {k: v for k, v in freeze.items() if k != "freeze_id"}
    config = freeze["config"]
    design, settings = Design(**config["design"]), Settings(**config["provider_settings"])
    if (identity(content) != freeze["freeze_id"] or source_commit() != freeze["source_commit"]
            or fingerprint(tasks, design) != freeze["provenance"]
            or asdict(settings) != freeze["provider_settings"]
            or config.get("live_calls_enabled") is not True
            or config.get("status") != "authorized_development_pilot"
            or config.get("authorization_reference") != freeze["authorization_reference"]
            or not freeze["authorization_reference"]
            or not re.fullmatch(r"[a-z][a-z0-9-]{5,100}", config.get("campaign_id", ""))
            or dollars(config["monetary_authorization_usd"]) != dollars(freeze["authorized_limit_usd"])
            or not settings.reserve * len(schedule_for(tasks, design, config)) * design.prefix_attempts * (1 + 2 * design.draws_per_action) <= dollars(freeze["authorized_limit_usd"]) <= 5):
        raise ValueError("Source, tasks, settings or authorization differ from the freeze")
    check_continuation(config, tasks, design)
    return design


def live_collect(freeze: dict, tasks: list[RepairTask], output: Path, *, claim_root: Path | None = None) -> dict:
    design = validate_freeze(freeze, tasks)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("Set OPENROUTER_API_KEY privately in the process environment")
    verifier = RepairVerifier()
    verifier.preflight()
    if output.exists():
        raise ValueError("Existing output cannot be resumed")
    claims = claim_root or Path(__file__).resolve().parents[3] / "runs" / "repair-pilot-admissions"
    claims.mkdir(parents=True, exist_ok=True)
    save(claims / (freeze["config"]["campaign_id"] + ".json"), {
         "freeze_id": freeze["freeze_id"], "output": str(output.resolve()),
         "created_at": datetime.now(timezone.utc).isoformat(), "resume_allowed": False})
    if freeze["config"].get("continuation"):
        save(claims / ("continuation-" + freeze["config"]["continuation"]["parent_freeze_id"] + ".json"), {
             "freeze_id": freeze["freeze_id"], "output": str(output.resolve()), "single_successor_only": True})
    return collect(tasks, design, output, verifier, lambda out: OpenRouterTransport(
        out, key, Settings(**freeze["provider_settings"]), authorized_limit_usd=freeze["authorized_limit_usd"]),
        freeze=freeze)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "demo", "audit", "compare", "freeze", "live"), default="plan", nargs="?")
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    if args.action in {"plan", "freeze"}:
        config = json.loads(args.config.read_text())
        design = Design(**config["design"])
        tasks = [task for _, task, _ in read_pool(args.pool)]
        settings = Settings(**config["provider_settings"])
        scheduled = len(schedule_for(tasks, design, config))
        maximum_calls = scheduled * design.prefix_attempts * (1 + 2 * design.draws_per_action)
        carried = check_continuation(config, tasks, design)
        result = {"mode": "plan_only", "api_calls": 0, "live_mode_requires_funded_freeze": True,
                  "tasks": len(tasks), "scheduled_trajectories": scheduled, "design": asdict(design), "maximum_calls": maximum_calls,
                  "task_hashes": [t.task_hash for t in tasks],
                  "proposed_provider_settings": asdict(settings), "reserved_usd_per_call": str(settings.reserve),
                  "maximum_reserved_usd": str(settings.reserve * maximum_calls),
                  "carried_committed_usd": str(carried),
                  "maximum_cumulative_committed_usd": str(carried + settings.reserve * maximum_calls),
                  "budget_authorized": config.get("monetary_authorization_usd") is not None,
                  "launch_enabled_by_config": config.get("live_calls_enabled") is True,
                  "next_step": ("Authorize the documented manual exception within the existing cumulative cap, commit and freeze." if config.get("continuation") else
                                "Obtain or verify the explicit cap, commit source, freeze the funded config, then collect once.")}
        if args.action == "freeze":
            if not args.output:
                parser.error("freeze requires --config with new authorization and a fresh --output file")
            result = funded_freeze(config, tasks, args.output)
    elif args.action == "demo":
        if not args.bundle or not args.output:
            parser.error("demo requires --bundle and fresh --output")
        result = demo(args.bundle, args.output)
    elif args.action == "live":
        if not args.input or not args.output:
            parser.error("live requires --input funded freeze and a fresh --output directory")
        result = live_collect(json.loads(args.input.read_text()), [t for _, t, _ in read_pool(args.pool)], args.output)
    else:
        if not args.input:
            parser.error("audit/compare require --input")
        result = audit(args.input) if args.action == "audit" else {"model_results": json.loads(
                  (args.input / "manifest.json").read_text())["model_results"],
                  "comparisons": comparisons(args.input), "api_calls": 0}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
