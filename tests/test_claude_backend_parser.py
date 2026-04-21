from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.agents.claude_parser import (
    ModelOutputError,
    parse_edit_payload,
    parse_json_object,
    parse_mode_distribution,
    repair_distribution_payload,
    validate_candidate_source,
)
from vao.prompts import render_template
from vao.taxonomy import MODES


FIXTURES = Path(__file__).parent / "fixtures"


def test_claude_cli_distribution_fixture_parses_and_normalizes() -> None:
    raw = (FIXTURES / "claude_distribution_cli.json").read_text(encoding="utf-8")
    dist = parse_mode_distribution(raw)
    assert set(dist.mode_probs) == set(MODES)
    assert abs(sum(dist.mode_probs.values()) - 1.0) < 1e-12
    assert dist.mode_ranking[0] == "indexing"


def test_claude_cli_edit_fixture_parses_safe_source() -> None:
    raw = (FIXTURES / "claude_edit_cli.json").read_text(encoding="utf-8")
    payload = parse_edit_payload(raw, "layout")
    assert payload["declared_mode"] == "layout"
    assert "class CandidateQueryEngine" in payload["solution_py"]
    assert payload["source_validation"]["passed"] is True


def test_invalid_probability_normalization_repair() -> None:
    payload = {
        "mode_probs": {mode: 2 for mode in MODES},
        "mode_ranking": list(reversed(MODES)),
        "mode_rationales": {mode: "" for mode in MODES},
    }
    repaired, failures = repair_distribution_payload(payload)
    assert failures == []
    assert sum(repaired["mode_probs"].values()) == pytest.approx(1.0)


def test_missing_mode_repair() -> None:
    payload = {
        "mode_probs": {"layout": 1, "indexing": 2, "topk": 1, "caching": 1, "summaries": 1},
        "mode_ranking": ["indexing"],
        "mode_rationales": {},
    }
    repaired, failures = repair_distribution_payload(payload)
    assert "missing_mode_prob:micro" in failures
    assert set(repaired["mode_probs"]) == set(MODES)
    assert set(repaired["mode_ranking"]) == set(MODES)


def test_invalid_candidate_source_rejection() -> None:
    invalid = "import os\nclass CandidateQueryEngine:\n    pass\n"
    validation = validate_candidate_source(invalid)
    assert validation["passed"] is False
    assert any("disallowed import" in item for item in validation["errors"])
    with pytest.raises(ModelOutputError):
        parse_edit_payload(json.dumps({"declared_mode": "layout", "solution_py": invalid, "rationale": "bad"}), "layout")


def test_prompt_template_rendering() -> None:
    rendered = render_template(
        "mode_distribution.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine: pass",
    )
    assert "layout" in rendered
    assert "mode_ranking" in rendered
    assert "CandidateQueryEngine" in rendered


def test_parse_json_object_from_fenced_text() -> None:
    assert parse_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}
