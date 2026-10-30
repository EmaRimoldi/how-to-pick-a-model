"""Fresh two-arm public-trace development calibration after solver compatibility."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import random
import zipfile

from .contracts import QWEN_TRACE_STUDY, provenance, public_feedback, study_settings
from .diagnostics import acquire, binding, observe, project, selected_failure
from .environment import RepairTask, identity
from .records import save
from .verifier import RepairVerifier

from .diagnostic_study import SOURCE, ARCHIVE_SHA, source_records
from .solver_study import validate_origin as validate_previous_origins

ARMS = ("focused", "focused_trace")
DRAWS, SEED = 4, 43130
CARRY = Decimal("0.06942739")
PRIOR = "experiments/python-repair/checkpoint-environment/results/solver-qwen-20261026"
PRIOR_ARCHIVE_SHA = "b349586449d6b25b04e333dfc442b7e54f6c660ebf04a8baefc17c093af5474e"


def design():
    return {"arms": list(ARMS), "draws_per_arm": DRAWS, "seed": SEED,
            "source_contract": "json_current", "primary": "focused_trace_minus_focused",
            "screening": {"minimum_bugs_with_two_trace_successes": 3,
                          "minimum_net_trace_successes": 4, "positive_in_each_two_draw_half": True},
            "fit_selector": False}


def schedule(records):
    pairs = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r["eligible"]]
    random.Random(SEED).shuffle(pairs)
    orders = list(itertools.permutations(ARMS))
    random.Random(SEED + 1).shuffle(orders)
    return [(i, draw, arm) for pos, (i, draw) in enumerate(pairs) for arm in orders[pos % len(orders)]]


def planned_requests(records):
    settings, _ = study_settings(QWEN_TRACE_STUDY)
    requests = []
    for index, draw, arm in schedule(records):
        record = records[index]
        task = RepairTask.from_dicts(record["public"], record["evaluator"])
        request = project(task.public, task.public["files"], record["observation"], arm, record["diagnostic"])
        request.update(mode="model_pilot", provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {"study": QWEN_TRACE_STUDY, "trajectory": f"{QWEN_TRACE_STUDY}-task-{index:03d}-draw-{draw}",
                "phase": "diagnostic_probe", "depth": 1, "draw": draw, "arm": arm,
                "contract": "json_current", "task_index": index, "task_hash": task.task_hash,
                "source_attempt_id": record["source_attempt_id"]}
        meta["attempt_id"] = identity(meta)
        requests.append({"metadata": meta, "request": request, "provider_body": settings.body(request, meta)})
    return requests


def construct(records, verifier):
    settings, limit = study_settings(QWEN_TRACE_STUDY)
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
    packet = {"schema_version": 1, "study": QWEN_TRACE_STUDY, "status": "draft_not_authorized",
        "api_calls": 0, "model_results": False, "live_calls_enabled": False,
        "monetary_authorization_usd": None, "provider_settings": asdict(settings),
        "design": design(), "source_archive_sha256": ARCHIVE_SHA,
        "source_result": SOURCE, "prior_result": PRIOR, "prior_archive_sha256": PRIOR_ARCHIVE_SHA, "source_provenance": provenance(tasks, QWEN_TRACE_STUDY),
        "verifier_preflight": preflight, "tasks": prepared, "requests": requests,
        "maximum_calls": len(requests), "maximum_new_reservations_usd": str(maximum),
        "proposed_cap_usd": str(limit), "reservation_usd": str(settings.reserve),
        "closed_pilot_commitment_usd": str(CARRY),
        "maximum_cumulative_commitment_usd": str(maximum + CARRY)}
    packet["packet_id"] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(QWEN_TRACE_STUDY)
    if (packet["study"] != QWEN_TRACE_STUDY or packet["schema_version"] != 1
            or packet["packet_id"] != identity({k: v for k, v in packet.items() if k != "packet_id"})
            or packet["status"] != "draft_not_authorized" or packet["api_calls"] != 0
            or packet["model_results"] or packet["live_calls_enabled"]
            or packet["monetary_authorization_usd"] is not None):
        raise ValueError("Invalid offline information-study packet")
    if (packet["design"] != design() or packet["provider_settings"] != asdict(settings)
            or packet["source_archive_sha256"] != ARCHIVE_SHA or packet["source_result"] != SOURCE
            or packet["prior_result"] != PRIOR or packet["prior_archive_sha256"] != PRIOR_ARCHIVE_SHA):
        raise ValueError("Frozen information design or source differs")
    records = packet["tasks"]
    if len(records) != 12 or sum(r["eligible"] for r in records) != 8:
        raise ValueError("Expected twelve retained candidates and eight public failures")
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
    if packet["requests"] != expected or len(expected) != 64 or packet["maximum_calls"] != len(expected):
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
    return {"maximum_calls": len(expected), "retained_candidates": len(records), "eligible": 8}


def validate_origin(packet):
    # Includes all prior source/information/interface planned bodies, even unsent.
    validate_previous_origins(packet)
    archive = Path(PRIOR) / "evidence.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PRIOR_ARCHIVE_SHA:
        raise ValueError("Closed solver archive changed")
    with zipfile.ZipFile(archive) as zipped:
        old = json.loads(zipped.read("collection/manifest.json"))["freeze"]["packet"]["requests"]
    if ({r["metadata"]["attempt_id"] for r in old} & {r["metadata"]["attempt_id"] for r in packet["requests"]}
            or {identity(r["provider_body"]) for r in old} & {identity(r["provider_body"]) for r in packet["requests"]}):
        raise ValueError("New experiment repeats a solver-control request")


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
