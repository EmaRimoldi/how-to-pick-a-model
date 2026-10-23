"""Verify published BigCodeBench evidence offline without executing candidate code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

if __package__:
    from .analyze_feedback_routing import analyze, audit, records
    from .report_feedback_routing import accounting_diagnostics
else:
    from analyze_feedback_routing import analyze, audit, records
    from report_feedback_routing import accounting_diagnostics


def equivalent(actual, expected, location="root"):
    """Compare every field, allowing only cross-platform floating point noise."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), location
        for key in expected:
            equivalent(actual[key], expected[key], location + "." + key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), location
        for i, (left, right) in enumerate(zip(actual, expected)):
            equivalent(left, right, f"{location}[{i}]")
    elif isinstance(expected, float):
        assert type(actual) in (int, float) and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), location
    else:
        assert type(actual) is type(expected) and actual == expected, location


def checked_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    assert path.is_relative_to(root.resolve()) and path != root.resolve(), name
    return path


def checksum_audit(root: Path):
    expected = json.loads((root / "checksums.json").read_text())
    files = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p != root / "checksums.json"}
    assert files == set(expected), "Published file set differs from checksum manifest"
    for name, digest in expected.items():
        assert hashlib.sha256(checked_path(root, name).read_bytes()).hexdigest() == digest, name


def verify_interim(root: Path):
    record = json.loads((root / "interim-record.json").read_text())
    calls = set(record["included_call_ids"])
    outcomes = {tuple(k) for k in record["included_outcome_keys"]}
    subset = {
        "budget.jsonl": records(root / "budget.jsonl")[:record["budget_journal_event_count"]],
        "calls.jsonl": [r for r in records(root / "calls.jsonl") if r["call"] in calls],
        "evaluations.jsonl": [r for r in records(root / "evaluations.jsonl") if r["call"] in calls],
        "outcomes.jsonl": [r for r in records(root / "outcomes.jsonl") if (r["task_id"], r["replicate"], r["policy"]) in outcomes],
        "transport.jsonl": [],
    }
    assert len(subset["calls.jsonl"]) == len(calls)
    assert len(subset["evaluations.jsonl"]) == len(calls)
    assert len(subset["outcomes.jsonl"]) == len(outcomes)
    for name, digest in record["source_snapshot_checksums"].items():
        content = ("".join(json.dumps(r, sort_keys=True) + "\n" for r in subset[name]).encode()
                   if name in subset else (root / name).read_bytes())
        assert hashlib.sha256(content).hexdigest() == digest, "Interim snapshot changed: " + name


def verify(root: Path) -> dict:
    checksum_audit(root)
    data = audit(root)
    equivalent(json.loads((root / "analysis.json").read_text()), analyze(data), "analysis")
    equivalent(json.loads((root / "accounting-diagnostics.json").read_text()), accounting_diagnostics(data), "accounting")
    source_map = json.loads((root / "source-map.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    assert source_map["git_commit"] == manifest["git_commit"]
    assert source_map["files"].keys() == data["config"]["source_hashes"].keys()
    for name, digest in data["config"]["source_hashes"].items():
        row = source_map["files"][name]
        assert row["sha256"] == digest
        assert hashlib.sha256(checked_path(root, row["snapshot"]).read_bytes()).hexdigest() == digest
        # The currently imported collector/verifier/analyzer must still be the frozen implementation.
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, "Source drift: " + name
    diagnostic = source_map["postcollection_verification"]
    assert hashlib.sha256(checked_path(root, diagnostic["snapshot"]).read_bytes()).hexdigest() == diagnostic["sha256"]
    summary = json.loads((root / "summary.json").read_text())
    assert summary["status"] == "complete" and summary["stop_error"] is None and data["integrity"]["complete"]
    equivalent(summary["known_cost_usd"], data["integrity"]["known_usd"])
    equivalent(summary["unresolved_reservations_usd"], data["integrity"]["held_usd"])
    assert summary["observed_policy_outcomes"] == len(data["outcomes"])
    assert summary["tasks"] == len(data["tasks"]) and summary["replicates"] == data["config"]["replicates"]
    assert summary["collection_cap_usd"] == data["config"]["run_ceiling_usd"]
    calls = data["calls"]
    assert len({r["generation_id"] for r in calls}) == len(calls)
    assert all(r["seed_sent"] is None for r in calls)
    repeated = json.loads((root / "verification-repeat.json").read_text())
    scores = {r["call"]: r for r in data["evaluations"]}
    assert repeated["model_calls"] == 0 and all(repeated["probe"].values())
    assert repeated["checked_responses"] == len(repeated["rows"]) == len(scores)
    assert {r["call"] for r in repeated["rows"]} == set(scores)
    for row in repeated["rows"]:
        original = scores[row["call"]]
        if row.get("format_error_reproduced"):
            assert original["solution"] == "" and original["visible"]["status"] == "format_error"
            assert not original["visible"]["passed"] and original["heldout"] is None and row["mismatches"] == []
            continue
        assert row["task_id"] == original["task_id"]
        assert row["original_visible_passed"] == original["visible"]["passed"]
        assert row["original_heldout_passed"] == (original["heldout"]["passed"] if original["heldout"] else None)
        mismatches = [part + "_passed" for part in ("visible", "heldout") if row[f"original_{part}_passed"] != row[f"repeated_{part}_passed"]]
        assert row["mismatches"] == mismatches
    assert sum(bool(r["mismatches"]) for r in repeated["rows"]) == repeated["mismatching_responses"]
    verify_interim(root)
    return {"status": "verified", "tasks": len(data["tasks"]), "policy_outcomes": len(data["outcomes"]),
            "responses": len(calls), "known_usd": data["integrity"]["known_usd"],
            "held_usd": data["integrity"]["held_usd"], "frozen_source_files": len(source_map["files"]),
            "verifier_repeat_discrepancies": repeated["mismatching_responses"],
            "interim_snapshot_preserved": True, "model_calls": 0, "candidate_execution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.input), indent=2))


if __name__ == "__main__":
    main()
