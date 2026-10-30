"""Prepare a separately funded public-trace information experiment, never retry.

Existing transport, receipts, source freezes and cell audits are reused. The
new intervention, repeated schedule and report have their own study identity.
"""

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

from .contracts import GEMMA27B_STUDY, TRACE_STUDY, provenance, public_feedback, study_settings
from .diagnostics import ARMS, acquire, binding, observe, project, selected_failure
from .environment import RepairTask, canonical, identity
from .records import save
from .verifier import RepairVerifier

SOURCE = "experiments/python-repair/checkpoint-environment/results/contract-gemma27b-20261026"
ARCHIVE_SHA = "f2a3b228425ee98a8a5bbc0422f6bdb486d44eeb1a2a86d4cabeba309103c913"
DRAWS = 4
SEED = 43122


def design():
    return {"arms": list(ARMS), "draws_per_arm": DRAWS, "seed": SEED,
            "source_contract": "json_current", "primary": "focused_trace_minus_focused",
            "screening": {"minimum_bugs_with_two_trace_successes": 3,
                          "minimum_net_trace_successes": 4, "positive_in_each_two_draw_half": True},
            "fit_selector": False}


def without_times(value):
    if isinstance(value, dict):
        return {k: without_times(v) for k, v in value.items()
                if k not in {"verifier_seconds", "diagnostic_seconds"}}
    if isinstance(value, list):
        return [without_times(v) for v in value]
    return value


def source_records(source=Path(SOURCE)):
    """Read the complete frozen bank, preserving all twelve predefined candidates."""
    archive = source / "evidence.zip"
    manifest = json.loads((source / "evidence-manifest.json").read_text())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA or manifest["archive_sha256"] != ARCHIVE_SHA:
        raise ValueError("Source archive differs from the declared closed 27B bank")
    records = []
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(manifest["files"]):
            raise ValueError("Source archive members differ")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError("Source archive member changed")
        frozen = json.loads(z.read("collection/manifest.json"))["freeze"]
        if frozen["study"] != GEMMA27B_STUDY or "collection/pilot-completion.json" not in names:
            raise ValueError("Only the closed complete 27B bank is a source")
        packet = frozen["packet"]
        rows = [json.loads(line) for line in z.read("collection/observations.jsonl").splitlines()]
        if len(rows) != 36 or len({r["attempt_id"] for r in rows}) != 36:
            raise ValueError("Source bank is incomplete")
        for row in sorted(rows, key=lambda r: r["task_index"]):
            if row["contract"] != "json_current":
                continue
            old = packet["tasks"][row["task_index"]]
            prefix = f"collection/cells/{row['attempt_id']}/objects/"
            def obj(ref):
                return json.loads(z.read(prefix + ref + ".json"))
            # This particular source bank has twelve valid JSON artifacts. Fail
            # closed if that provenance changes; never replace/drop a candidate.
            if not row["artifact"] or not row["public"]:
                raise ValueError("Declared source candidate is absent")
            public = {**old["public"], "files": obj(row["artifact"])["files"]}
            records.append({"public": public, "evaluator": old["evaluator"],
                "source_attempt_id": row["attempt_id"], "source_task_hash": row["task_hash"],
                "source_artifact": row["artifact"], "source_cost_usd": row["cost_usd"],
                "source_public_result": public_feedback(obj(row["public"])["result"]),
                "source_full_pass": row["full_pass"]})
    if len(records) != 12 or len({r["public"]["task_id"] for r in records}) != 12:
        raise ValueError("All twelve original JSON candidates must be retained")
    return records


def schedule(records):
    pairs = [(i, draw) for draw in range(DRAWS) for i, r in enumerate(records) if r["eligible"]]
    random.Random(SEED).shuffle(pairs)
    orders = list(itertools.permutations(ARMS))
    random.Random(SEED + 1).shuffle(orders)
    return [(i, draw, arm) for pos, (i, draw) in enumerate(pairs) for arm in orders[pos % len(orders)]]


def planned_requests(records):
    settings, _ = study_settings(TRACE_STUDY)
    requests = []
    for index, draw, arm in schedule(records):
        record = records[index]
        task = RepairTask.from_dicts(record["public"], record["evaluator"])
        request = project(task.public, task.public["files"], record["observation"], arm, record["diagnostic"])
        request.update(mode="model_pilot", provider_call_enabled=True, remaining_budget_usd=str(settings.reserve))
        meta = {"study": TRACE_STUDY, "trajectory": f"{TRACE_STUDY}-task-{index:03d}-draw-{draw}",
                "phase": "diagnostic_probe", "depth": 1, "draw": draw, "arm": arm,
                "contract": "json_current", "task_index": index, "task_hash": task.task_hash,
                "source_attempt_id": record["source_attempt_id"]}
        meta["attempt_id"] = identity(meta)
        requests.append({"metadata": meta, "request": request, "provider_body": settings.body(request, meta)})
    return requests


def construct(records, verifier):
    settings, limit = study_settings(TRACE_STUDY)
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
    packet = {"schema_version": 1, "study": TRACE_STUDY, "status": "draft_not_authorized",
        "api_calls": 0, "model_results": False, "live_calls_enabled": False,
        "monetary_authorization_usd": None, "provider_settings": asdict(settings),
        "design": design(), "source_archive_sha256": ARCHIVE_SHA,
        "source_result": SOURCE, "source_provenance": provenance(tasks, TRACE_STUDY),
        "verifier_preflight": preflight, "tasks": prepared, "requests": requests,
        "maximum_calls": len(requests), "maximum_new_reservations_usd": str(maximum),
        "proposed_cap_usd": str(limit), "reservation_usd": str(settings.reserve),
        "closed_pilot_commitment_usd": "0.02211715",
        "maximum_cumulative_commitment_usd": str(maximum + Decimal("0.02211715"))}
    packet["packet_id"] = identity(packet)
    validate_packet(packet)
    return packet


def validate_packet(packet):
    settings, limit = study_settings(TRACE_STUDY)
    if (packet["study"] != TRACE_STUDY or packet["schema_version"] != 1
            or packet["packet_id"] != identity({k: v for k, v in packet.items() if k != "packet_id"})
            or packet["status"] != "draft_not_authorized" or packet["api_calls"] != 0
            or packet["model_results"] or packet["live_calls_enabled"]
            or packet["monetary_authorization_usd"] is not None):
        raise ValueError("Invalid offline information-study packet")
    if (packet["design"] != design() or packet["provider_settings"] != asdict(settings)
            or packet["source_archive_sha256"] != ARCHIVE_SHA or packet["source_result"] != SOURCE):
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
    if packet["requests"] != expected or len(expected) != 96 or packet["maximum_calls"] != len(expected):
        raise ValueError("Exact intervention, draw schedule or request projection differs")
    if len({r["metadata"]["attempt_id"] for r in expected}) != len(expected):
        raise ValueError("Duplicate attempt identity")
    maximum = len(expected) * settings.reserve
    if (packet["maximum_new_reservations_usd"] != str(maximum) or packet["reservation_usd"] != str(settings.reserve)
            or packet["proposed_cap_usd"] != str(limit) or maximum > limit
            or packet["closed_pilot_commitment_usd"] != "0.02211715"
            or packet["maximum_cumulative_commitment_usd"] != str(maximum + Decimal("0.02211715"))):
        raise ValueError("Information-study financial projection differs")
    return {"maximum_calls": len(expected), "retained_candidates": len(records), "eligible": 8}


def validate_origin(packet):
    source = source_records(Path(SOURCE))
    for original, prepared in zip(source, packet["tasks"]):
        if any(prepared[k] != v for k, v in original.items()):
            raise ValueError("Checkpoint differs from its immutable source")
    old_ids = {r["source_attempt_id"] for r in source}
    if old_ids & {r["metadata"]["attempt_id"] for r in packet["requests"]}:
        raise ValueError("New study repeats a historical admission")


def validate_diagnostics(packet, verifier):
    """Reproduce every public probe before provider preflight; never retune it."""
    for record in packet["tasks"]:
        public = record["public"]
        state = observe(public, public["files"], verifier)
        diagnostic = acquire(public, public["files"], state, verifier)
        if (without_times(state) != without_times(record["observation"])
                or without_times(diagnostic) != without_times(record["diagnostic"])):
            raise ValueError("Public diagnostic does not reproduce before launch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = construct(source_records(), RepairVerifier())
    save(args.output, packet)
    print(json.dumps({k: packet[k] for k in ("packet_id", "maximum_calls", "maximum_new_reservations_usd", "proposed_cap_usd")}))


if __name__ == "__main__":
    main()
