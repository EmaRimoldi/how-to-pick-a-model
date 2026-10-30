"""New independent-cell streaming study with a prospective robust development screen."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import zipfile

from .contracts import INDEPENDENT_TRACE_STUDY, provenance, public_feedback, study_settings
from .diagnostics import acquire, binding, observe, project, selected_failure
from .environment import RepairTask, identity
from .records import save
from .verifier import RepairVerifier

from .diagnostic_study import SOURCE, ARCHIVE_SHA, source_records
from .independent_streaming import POLICY

ARMS = ("focused", "focused_trace")
DRAWS, SEED = 4, 43136
CARRY = Decimal("0.12585127")
PRIOR = "experiments/python-repair/checkpoint-environment/results/information-stream-stopped-20261026"
PRIOR_ARCHIVE_SHA = "265123653e998438eabf9652406c58393d2daec590fd4aee3276e0282bd018ff"


def design():
    return {"arms": list(ARMS), "draws_per_arm": DRAWS, "seed": SEED,
            "source_contract": "json_current", "primary": "focused_trace_minus_focused",
            "screening": {"minimum_bugs_with_two_trace_successes": 3,
                          "minimum_net_trace_successes": 4, "positive_in_each_two_draw_half": True},
            "fit_selector": False, "wire_limit_bytes": 8388608,
            "transport_missing_policy": copy.deepcopy(POLICY), "historical_controls": False,
            "screening_missingness": "all_binary_completions_must_pass",
            "exposed_development_checkpoints": True}


def schedule(records):
    pairs = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r["eligible"]]
    random.Random(SEED).shuffle(pairs)
    orders = (ARMS, tuple(reversed(ARMS)))
    return [(i, draw, arm) for pos, (i, draw) in enumerate(pairs) for arm in orders[pos % len(orders)]]


def planned_requests(records):
    settings, _ = study_settings(INDEPENDENT_TRACE_STUDY)
    requests = []
    for index, draw, arm in schedule(records):
        record = records[index]
        task = RepairTask.from_dicts(record["public"], record["evaluator"])
        request = project(task.public, task.public["files"], record["observation"], arm, record["diagnostic"])
        request.update(mode="model_pilot", provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {"study": INDEPENDENT_TRACE_STUDY, "trajectory": f"{INDEPENDENT_TRACE_STUDY}-task-{index:03d}-draw-{draw}",
                "phase": "diagnostic_probe", "depth": 1, "draw": draw, "arm": arm,
                "contract": "json_current", "task_index": index, "task_hash": task.task_hash,
                "source_attempt_id": record["source_attempt_id"]}
        meta["attempt_id"] = identity(meta)
        requests.append({"metadata": meta, "request": request, "provider_body": settings.body(request, meta)})
    return requests


def construct(records, verifier):
    settings, limit = study_settings(INDEPENDENT_TRACE_STUDY)
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
    packet = {"schema_version": 1, "study": INDEPENDENT_TRACE_STUDY, "status": "draft_not_authorized",
        "api_calls": 0, "model_results": False, "live_calls_enabled": False,
        "monetary_authorization_usd": None, "provider_settings": asdict(settings),
        "design": design(), "source_archive_sha256": ARCHIVE_SHA,
        "source_result": SOURCE, "prior_result": PRIOR, "prior_archive_sha256": PRIOR_ARCHIVE_SHA, "source_provenance": provenance(tasks, INDEPENDENT_TRACE_STUDY),
        "verifier_preflight": preflight, "tasks": prepared, "requests": requests,
        "maximum_calls": len(requests), "maximum_new_reservations_usd": str(maximum),
        "proposed_cap_usd": str(limit), "reservation_usd": str(settings.reserve),
        "closed_pilot_commitment_usd": str(CARRY),
        "maximum_cumulative_commitment_usd": str(maximum + CARRY)}
    packet["packet_id"] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(INDEPENDENT_TRACE_STUDY)
    if (packet["study"] != INDEPENDENT_TRACE_STUDY or packet["schema_version"] != 1
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


HISTORY = {
    "experiments/python-repair/checkpoint-environment/results/contract-deepinfra-20261026/evidence.zip": "025e3d3fbc72f76caf3d880491d0bfa0af57153507c9379540646a14ef8a0c25",
    "experiments/python-repair/checkpoint-environment/results/contract-diagnostic-20261026/evidence.zip": "b9b88099e2d6988313696f8dbd0f8d253fe1834be50297ac105660f45274890b",
    "experiments/python-repair/checkpoint-environment/results/contract-gemma12b-20261026/evidence.zip": "0b076c5ea7dee254604c70ed6152379147921b4ee04e663f719b8859754720f7",
    "experiments/python-repair/checkpoint-environment/results/contract-gemma27b-20261026/evidence.zip": "f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913",
    "experiments/python-repair/checkpoint-environment/results/gemma4b-calibration-20261026/evidence.zip": "2809c117c743f27f645b94ec25d9aba312dbb1bef18f36c0dac7d10e39153546",
    "experiments/python-repair/checkpoint-environment/results/information-extension-stopped-20261026/evidence.zip": "99cca40cacf207d8e6fa26a81cb491f548c4fb52226beebcac351aceb61d13fa",
    "experiments/python-repair/checkpoint-environment/results/information-interrupted-20261026/evidence.zip": "f4241d9d1905a29e00b9c89a301570c72695fcf5605adc60a23b120948001e88",
    "experiments/python-repair/checkpoint-environment/results/information-qwen-stopped-20261026/evidence.zip": "3af83eea545078a008fa83527b758c73f42990ae0b6a14b993c87a29dcfcde06",
    "experiments/python-repair/checkpoint-environment/results/information-stopped-20261026/evidence.zip": "f6e6cad5035268a5015fa4db35943f67201e72480020d0efb3d6b2221486c0fe",
    "experiments/python-repair/checkpoint-environment/results/information-stream-stopped-20261026/evidence.zip": "265123653e998438eabf9652406c58393d2daec590fd4aee3276e0282bd018ff",
    "experiments/python-repair/checkpoint-environment/results/interface-stopped-20261026/evidence.zip": "cecb09caa99ce851d1ca1df1f5e6bf719ea43fcdd166f5428af52da30dc0eb59",
    "experiments/python-repair/checkpoint-environment/results/solver-qwen-20261026/evidence.zip": "b349586449d6b25b04e333dfc442b7e54f6c660ebf04a8baefc17c093af5474e",
    "experiments/python-repair/checkpoint-environment/results/sse-compatibility-20261026/evidence.zip": "4f746966054f585017c7c1490cab6ed28ee387b153791a99cca1320ba1e8a47e",
    "experiments/python-repair/checkpoint-environment/results/sse-wire-envelope-20261026/evidence.zip": "2baf7a00a7fc76d7e49c7027a5b2d9716fe9cf3b642b56fe6bf73d285ca7e5e1"
}


def archived_requests(value):
    """Include planned unsent requests and nested historical segments."""
    if isinstance(value, dict):
        if isinstance(value.get("provider_body"), dict) and isinstance(value.get("metadata"), dict) and value["metadata"].get("attempt_id"):
            yield value
        for child in value.values():
            yield from archived_requests(child)
    elif isinstance(value, list):
        for child in value:
            yield from archived_requests(child)


def validate_origin(packet):
    originals = source_records()
    if len(originals) != len(packet["tasks"]):
        raise ValueError("Source candidate count differs")
    for original, record in zip(originals, packet["tasks"]):
        if any(record.get(k) != v for k, v in original.items()):
            raise ValueError("Source candidate content or provenance differs")
    old_ids, old_bodies = set(), set()
    for name, expected in HISTORY.items():
        archive = Path(name)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError("Historical archive changed")
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.namelist():
                if member.startswith("collection/") and member.endswith("/manifest.json"):
                    for old in archived_requests(json.loads(zipped.read(member))):
                        old_ids.add(old["metadata"]["attempt_id"])
                        old_bodies.add(identity(old["provider_body"]))
    if (old_ids & {r["metadata"]["attempt_id"] for r in packet["requests"]}
            or old_bodies & {identity(r["provider_body"]) for r in packet["requests"]}):
        raise ValueError("New study repeats a historical planned request")
    return {"historical_archives": len(HISTORY), "historical_unique_bodies": len(old_bodies),
            "historical_overlap": 0, "source_candidates_verified": len(originals)}


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
