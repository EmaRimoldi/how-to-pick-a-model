"""Reject altered reports/files; reproduce the released bank without live inference."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_feedback_evidence import checksum_audit, equivalent, source_audit, verify


def test_statistics_comparison_rejects_changed_result_and_accepts_roundoff():
    equivalent({"estimate": .1 + .2, "passed": False}, {"estimate": .3, "passed": False})
    with pytest.raises(AssertionError, match="estimate"):
        equivalent({"estimate": .31}, {"estimate": .3})
    with pytest.raises(AssertionError):
        equivalent({"passed": 0}, {"passed": False})


def test_checksum_audit_rejects_tampering_and_undeclared_file(tmp_path):
    report = tmp_path / "report.md"
    report.write_text("original")
    (tmp_path / "checksums.json").write_text(json.dumps({"report.md": hashlib.sha256(report.read_bytes()).hexdigest()}))
    checksum_audit(tmp_path)
    report.write_text("edited")
    with pytest.raises(AssertionError, match="report.md"):
        checksum_audit(tmp_path)
    report.write_text("original")
    (tmp_path / "extra").write_text("unlisted")
    with pytest.raises(AssertionError, match="file set"):
        checksum_audit(tmp_path)


def test_canonical_bank_reproduces_outside_checkout(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    bank = root / "experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022"
    monkeypatch.chdir(tmp_path)
    result = verify(bank)
    assert result["status"] == "verified" and result["policy_outcomes"] == 628
    assert result["verifier_repeat_discrepancies"] == 0 and result["model_calls"] == 0


def test_source_provenance_accepts_runtime_evolution_but_rejects_snapshot_drift(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("collector.py").write_text("maintained runtime")
    frozen = tmp_path / "frozen.txt"
    frozen.write_text("original collector")
    digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
    source_map = {"git_commit": "collection-commit",
                  "files": {"collector.py": {"sha256": digest, "snapshot": "frozen.txt"}},
                  "postcollection_verification": {"sha256": digest, "snapshot": "frozen.txt"}}
    (tmp_path / "source-map.json").write_text(json.dumps(source_map))
    config = {"source_hashes": {"collector.py": digest}}
    manifest = {"git_commit": "collection-commit"}
    assert source_audit(tmp_path, config, manifest) == 1
    frozen.write_text("altered evidence")
    with pytest.raises(AssertionError):
        source_audit(tmp_path, config, manifest)
