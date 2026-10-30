"""Independent three-bug development calibration; no historical bank is resumed."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import random
import zipfile

from .contracts import EXTENSION_TRACE_STUDY, provenance, public_feedback, study_settings
from .diagnostics import acquire, binding, observe, project, selected_failure
from .environment import RepairTask, identity
from .records import save
from .verifier import RepairVerifier

from .pool import read_pool
from .independent_transport import POLICY

SOURCE = "experiments/python-repair/checkpoint-environment/development-extension"
POOL_SHA = "4563c180054877014eae90283fb50c00f968950a8c6c8f39e7eb95e118f5a4ad"

ARMS = ("focused", "focused_trace")
DRAWS, SEED = 4, 43131
CARRY = Decimal("0.08592275")
PRIOR = "experiments/python-repair/checkpoint-environment/results/information-qwen-stopped-20261026"
PRIOR_ARCHIVE_SHA = "3af83eea545078a008fa83527b758c73f42990ae0b6a14b993c87a29dcfcde06"


def design():
    return {"arms": list(ARMS), "draws_per_arm": DRAWS, "seed": SEED,
            "source_contract": "json_current", "primary": "focused_trace_minus_focused",
            "screening": {"minimum_bugs_with_two_trace_successes": 3,
                          "minimum_net_trace_successes": 4, "positive_in_each_two_draw_half": True},
            "fit_selector": False, "transport_missing_policy": copy.deepcopy(POLICY),
            "checkpoint_origin": "original_upstream_buggy_version_no_model_prefix"}


def schedule(records):
    pairs = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r["eligible"]]
    random.Random(SEED).shuffle(pairs)
    orders = list(itertools.permutations(ARMS))
    random.Random(SEED + 1).shuffle(orders)
    return [(i, draw, arm) for pos, (i, draw) in enumerate(pairs) for arm in orders[pos % len(orders)]]


def planned_requests(records):
    settings, _ = study_settings(EXTENSION_TRACE_STUDY)
    requests = []
    for index, draw, arm in schedule(records):
        record = records[index]
        task = RepairTask.from_dicts(record["public"], record["evaluator"])
        request = project(task.public, task.public["files"], record["observation"], arm, record["diagnostic"])
        request.update(mode="model_pilot", provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {"study": EXTENSION_TRACE_STUDY, "trajectory": f"{EXTENSION_TRACE_STUDY}-task-{index:03d}-draw-{draw}",
                "phase": "diagnostic_probe", "depth": 1, "draw": draw, "arm": arm,
                "contract": "json_current", "task_index": index, "task_hash": task.task_hash,
                "source_attempt_id": record["source_attempt_id"]}
        meta["attempt_id"] = identity(meta)
        requests.append({"metadata": meta, "request": request, "provider_body": settings.body(request, meta)})
    return requests


def construct(records, verifier):
    settings, limit = study_settings(EXTENSION_TRACE_STUDY)
    preflight = verifier.preflight()
    prepared = []
    for source in records:
        task = RepairTask.from_dicts(source["public"], source["evaluator"])
        observation = observe(task.public, task.public["files"], verifier)
        if observation["feedback"] != source["source_public_result"]:
            raise ValueError("Saved source public outcomes do not reproduce")
        diagnostic = acquire(task.public, task.public["files"], observation, verifier)
        eligible = not observation["feedback"]["passed"]
        prepared.append({**source, "task_hash": task.task_hash,
            "initial_public_result": {**observation["feedback"], "verifier_seconds": observation["verifier_seconds"]},
            "observation": observation, "diagnostic": diagnostic, "eligible": eligible,
            "eligibility_reason": "public_failure" if eligible else "public_pass_no_repair_trigger"})
    tasks = [RepairTask.from_dicts(r["public"], r["evaluator"]) for r in prepared]
    requests = planned_requests(prepared)
    maximum = len(requests) * settings.reserve
    if maximum > limit:
        raise ValueError("Study limit cannot cover all reserved requests")
    packet = {"schema_version": 1, "study": EXTENSION_TRACE_STUDY, "status": "draft_not_authorized",
        "api_calls": 0, "model_results": False, "live_calls_enabled": False,
        "monetary_authorization_usd": None, "provider_settings": asdict(settings),
        "design": design(), "source_pool_sha256": POOL_SHA,
        "source_result": SOURCE, "prior_result": PRIOR, "prior_archive_sha256": PRIOR_ARCHIVE_SHA, "source_provenance": provenance(tasks, EXTENSION_TRACE_STUDY),
        "verifier_preflight": preflight, "tasks": prepared, "requests": requests,
        "maximum_calls": len(requests), "maximum_new_reservations_usd": str(maximum),
        "proposed_cap_usd": str(limit), "reservation_usd": str(settings.reserve),
        "closed_pilot_commitment_usd": str(CARRY),
        "maximum_cumulative_commitment_usd": str(maximum + CARRY)}
    packet["packet_id"] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(EXTENSION_TRACE_STUDY)
    if (packet["study"] != EXTENSION_TRACE_STUDY or packet["schema_version"] != 1
            or packet["packet_id"] != identity({k: v for k, v in packet.items() if k != "packet_id"})
            or packet["status"] != "draft_not_authorized" or packet["api_calls"] != 0
            or packet["model_results"] or packet["live_calls_enabled"]
            or packet["monetary_authorization_usd"] is not None):
        raise ValueError("Invalid offline information-study packet")
    if (packet["design"] != design() or packet["provider_settings"] != asdict(settings)
            or packet["source_pool_sha256"] != POOL_SHA or packet["source_result"] != SOURCE
            or packet["prior_result"] != PRIOR or packet["prior_archive_sha256"] != PRIOR_ARCHIVE_SHA):
        raise ValueError("Frozen information design or source differs")
    records = packet["tasks"]
    if len(records) != 3 or sum(r["eligible"] for r in records) != 3:
        raise ValueError("Expected all three additional development candidates and their public failures")
    for record in records:
        task = RepairTask.from_dicts(record["public"], record["evaluator"])
        if task.task_hash != record["task_hash"]:
            raise ValueError("Candidate task identity changed")
        state = record["observation"]
        selected = selected_failure(task.public, task.public["files"], state)
        eligible = selected is not None
        if (record["eligible"] != eligible or state["feedback"]["passed"] == eligible
                or state["feedback"] != record["source_public_result"]
                or state["feedback"] != public_feedback(record["initial_public_result"])
                or record["diagnostic"]["binding"] != binding(task.public, task.public["files"])):
            raise ValueError("Public-only eligibility or diagnostic binding differs")
        if record["eligibility_reason"] != ("public_failure" if eligible else "public_pass_no_repair_trigger"):
            raise ValueError("Eligibility reason differs")
    expected = planned_requests(records)
    if packet["requests"] != expected or len(expected) != 24 or packet["maximum_calls"] != len(expected):
        raise ValueError("Exact intervention, draw schedule or request projection differs")
    if (len({r["metadata"]["attempt_id"] for r in expected}) != len(expected)
            or len({identity(r["provider_body"]) for r in expected}) != len(expected)):
        raise ValueError("Duplicate attempt identity")
    maximum = len(expected) * settings.reserve
    if (packet["maximum_new_reservations_usd"] != str(maximum) or packet["reservation_usd"] != str(settings.reserve)
            or packet["proposed_cap_usd"] != str(limit) or maximum > limit
            or packet["closed_pilot_commitment_usd"] != str(CARRY)
            or packet["maximum_cumulative_commitment_usd"] != str(maximum + CARRY)):
        raise ValueError("Information-study financial projection differs")
    return {"maximum_calls": len(expected), "retained_candidates": len(records), "eligible": 3}


def source_records():
    root = Path(SOURCE)
    if hashlib.sha256((root / "pool.json").read_bytes()).hexdigest() != POOL_SHA:
        raise ValueError("Reviewed development extension changed")
    qualification = json.loads((root / "qualification.json").read_text())
    if qualification["pool_sha256"] != POOL_SHA or qualification["qualified"] != 3:
        raise ValueError("Development pool must have the recorded qualification")
    qualified = {r["id"]: r for r in qualification["tasks"]}
    records = []
    for slug, task, _ in read_pool(root):
        q = qualified[slug]
        if not q["engineering_qualified"] or q["task_hash"] != task.task_hash:
            raise ValueError("Qualified task identity differs")
        result = q["outcomes"]["initial"]["public"]
        result = {"passed": result["passed_cases"] == result["total_cases"], **result}
        records.append({"public": task.public, "evaluator": json.loads(task.evaluator_json),
            "source_attempt_id": "upstream-initial-" + task.task_hash,
            "source_task_hash": task.task_hash, "source_artifact": identity(task.public["files"]),
            "source_cost_usd": "0", "source_public_result": result, "source_full_pass": False})
    return records


def validate_origin(packet):
    originals = source_records()
    if len(originals) != len(packet["tasks"]):
        raise ValueError("Development source count differs")
    for source, record in zip(originals, packet["tasks"], strict=True):
        if any(record.get(k) != v for k, v in source.items()):
            raise ValueError("Independent development checkpoint changed")
    archive = Path(PRIOR) / "evidence.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PRIOR_ARCHIVE_SHA:
        raise ValueError("Closed information evidence changed")
    with zipfile.ZipFile(archive) as zipped:
        old = json.loads(zipped.read("collection/manifest.json"))["freeze"]["packet"]
    old_bugs = {r["public"]["provenance"]["benchmark_id"] for r in old["tasks"]}
    new_bugs = {r["public"]["provenance"]["benchmark_id"] for r in originals}
    if old_bugs & new_bugs:
        raise ValueError("This independent study cannot reuse closed study checkpoints")
    if ({r["metadata"]["attempt_id"] for r in old["requests"]} & {r["metadata"]["attempt_id"] for r in packet["requests"]}
            or {identity(r["provider_body"]) for r in old["requests"]} & {identity(r["provider_body"]) for r in packet["requests"]}):
        raise ValueError("New design repeats an old planned request")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = construct(source_records(), RepairVerifier())
    validate_origin(packet)
    save(args.output, packet)
    print(json.dumps({k: packet[k] for k in ("packet_id", "maximum_calls", "maximum_new_reservations_usd", "proposed_cap_usd")}))


if __name__ == "__main__":
    main()
