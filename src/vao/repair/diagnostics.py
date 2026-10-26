"""Public-only diagnostic acquisition and matched offline prompt projections.

This is an engineering component, not a fitted policy or a live collector.
Callers pass public task data, never a RepairTask with evaluator cases.
"""

from __future__ import annotations

import re
import time

from .environment import REPAIR_SYSTEM, canonical, identity, validate_cases, validate_files

ARMS = ("raw", "focused", "focused_trace")


def validate_public(public, files):
    if set(public) != {"schema_version", "task_id", "instruction", "entrypoint", "files", "public_cases", "provenance"}:
        raise ValueError("Only the public task schema is accepted")
    if public["schema_version"] != 1 or not isinstance(public["instruction"], str):
        raise ValueError("Unsupported public task")
    validate_files(public["files"])
    validate_files(files)
    validate_cases(public["public_cases"])
    if set(files) != set(public["files"]):
        raise ValueError("Artifact files differ from declared workspace")
    entry = public["entrypoint"]
    if (set(entry) != {"module", "function"} or any(
            not isinstance(v, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", v) for v in entry.values())
            or entry["module"] + ".py" not in files):
        raise ValueError("Invalid entrypoint")


def binding(public, files):
    # Exclude provenance URLs and task labels from solver-facing evidence.
    return identity({"instruction": public["instruction"], "entrypoint": public["entrypoint"],
                     "public_cases": public["public_cases"], "files": files})


def observe(public, files, verifier):
    """Run the existing public suite; this is shared checkpoint work, not treatment."""
    validate_public(public, files)
    result = verifier.check(files, public["entrypoint"], public["public_cases"])
    feedback = {k: result[k] for k in ("passed", "passed_cases", "total_cases", "cases")}
    return {"binding": binding(public, files), "feedback": feedback,
            "verifier_seconds": result["verifier_seconds"]}


def selected_failure(public, files, observation):
    validate_public(public, files)
    if observation["binding"] != binding(public, files):
        raise ValueError("Feedback belongs to a different public state")
    rows = observation["feedback"]["cases"]
    if [r["id"] for r in rows] != [c["id"] for c in public["public_cases"]]:
        raise ValueError("Feedback is not the complete ordered public suite")
    for case, row in zip(public["public_cases"], rows):
        if not row["passed"]:
            return {"case": case, "observed": row["observed"]}
    return None


def acquire(public, files, observation, verifier):
    """Trace the first public failure, with ordinary re-execution for consistency.

    No public failure means no probe. An unavailable/mismatched trace stays
    unavailable; it cannot become an invented diagnosis or a reason to drop a row.
    """
    selected = selected_failure(public, files, observation)
    start = time.monotonic()
    report = {"binding": observation["binding"], "available": False,
              "reason": "no_public_failure", "additional_executions": 0}
    if selected is not None:
        case = selected["case"]
        ordinary = verifier.invoke(files, public["entrypoint"], case)
        traced = verifier.trace(files, public["entrypoint"], case)
        report.update({"case_id": case["id"], "additional_executions": 2,
                       "untraced_observation": ordinary, "trace_result": traced})
        same = (traced.get("available") is True
                and canonical(selected["observed"]) == canonical(ordinary)
                and canonical(ordinary) == canonical(traced.get("observed")))
        report["available"] = same
        report["reason"] = None if same else "trace_unavailable_or_observation_mismatch"
    report["diagnostic_seconds"] = time.monotonic() - start
    return report


def project(public, files, observation, arm, diagnostic=None):
    """Construct an inert prompt; no provider setting or API authorization exists."""
    if arm not in ARMS:
        raise ValueError("Unknown diagnostic arm")
    selected = selected_failure(public, files, observation)
    payload = {"instruction": public["instruction"], "entrypoint": public["entrypoint"],
               "files": files, "public_cases": public["public_cases"],
               "latest_feedback": observation["feedback"]}
    if arm != "raw":
        # Duplicate existing information; do not pretend this adds a new oracle.
        payload["focused_public_failure"] = selected
    if arm == "focused_trace":
        if diagnostic is None or diagnostic["binding"] != observation["binding"]:
            raise ValueError("A matching diagnostic record is required")
        payload["runtime_diagnostic"] = {
            "available": diagnostic["available"], "reason": diagnostic["reason"],
            "trace": diagnostic["trace_result"]["trace"] if diagnostic["available"] else None}
    return {"messages": [{"role": "system", "content": REPAIR_SYSTEM},
                         {"role": "user", "content": canonical(payload)}],
            "provider_call_enabled": False, "mode": "offline_diagnostic_preparation"}
