"""Reject altered reports/files; reproduce the released bank without live inference."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_feedback_evidence import checksum_audit, equivalent, verify


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


def test_canonical_bank_reproduces_all_reports_sources_and_interim_prefix():
    result = verify(Path("experiments/bigcodebench/feedback-only-routing/results/fixed-policies-20261022"))
    assert result["status"] == "verified" and result["policy_outcomes"] == 628
    assert result["verifier_repeat_discrepancies"] == 0 and result["model_calls"] == 0
