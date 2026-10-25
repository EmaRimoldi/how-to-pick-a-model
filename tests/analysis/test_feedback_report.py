"""No outcome analysis while active; published evidence remains tied to its freeze."""

import json
from pathlib import Path

import pytest

from vao.analysis.report_feedback_routing import publish, report_text


def test_publication_refuses_active_collection_without_creating_output(tmp_path):
    source = tmp_path / "active"
    source.mkdir()
    target = tmp_path / "publication"
    with pytest.raises(RuntimeError, match="has not ended"):
        publish(source, target)
    assert not target.exists()


def test_incomplete_report_discloses_unknowns_without_calling_it_equivalence():
    report = {"status": "incomplete_descriptive_bank", "task_clusters": 157, "replicates": 1,
              "primary_gate_passed": False, "policies": {},
              "contrasts": [{"estimate": None, "all_selected_missing_bounds": [-1, 1]}],
              "integrity": {"known_usd": .2, "held_usd": .00512}}
    text = report_text(report)
    assert "Incomplete bank" in text and "not confidence intervals" in text
    assert "not passed" in text and "does not establish equivalence" in text
    assert "not a feedback-versus-no-feedback test" in text
