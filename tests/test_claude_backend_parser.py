from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.agents.claude_parser import (
    ModelOutputError,
    parse_edit_payload,
    parse_json_object,
    parse_mode_distribution,
    parse_replacement_payload,
    repair_distribution_payload,
    validate_candidate_source,
)
from vao.patches import PatchApplyError, apply_unified_diff
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
    parent_source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    payload = parse_edit_payload(raw, "layout", parent_source=parent_source)
    assert payload["primary_mode"] == "layout"
    assert payload["declared_mode"] == "layout"
    assert payload["edit_format"] == "unified_diff"
    assert payload["patch_parse_status"] == "passed"
    assert payload["patch_apply_status"] == "passed"
    assert payload["source_validation_status"] == "passed"
    assert "class CandidateQueryEngine" in payload["solution_py"]
    assert "Layout candidate retaining" in payload["solution_py"]
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


def test_full_replacement_source_is_rejected_even_if_valid() -> None:
    valid_replacement = "class CandidateQueryEngine:\n    pass\n"
    raw = json.dumps(
        {
            "primary_mode": "layout",
            "declared_mode": "layout",
            "edit_format": "unified_diff",
            "solution_py": valid_replacement,
            "rationale": "bad",
        }
    )
    with pytest.raises(ModelOutputError, match="replacement_file_output_not_allowed"):
        parse_edit_payload(raw, "layout", parent_source=valid_replacement)


def test_replacement_payload_parser_accepts_explicit_replacement_protocol() -> None:
    source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    raw = json.dumps(
        {
            "primary_mode": "layout",
            "declared_mode": "layout",
            "edit_format": "replacement_file",
            "secondary_modes": [],
            "rationale": "Replacement protocol candidate.",
            "solution_py": source,
        }
    )
    payload = parse_replacement_payload(raw, "layout")
    assert payload["source_validation_status"] == "passed"
    assert payload["patch_apply_status"] == "not_applicable_replacement"
    assert "class CandidateQueryEngine" in payload["solution_py"]


def test_primary_mode_mismatch_is_rejected() -> None:
    raw = (FIXTURES / "claude_edit_cli.json").read_text(encoding="utf-8")
    with pytest.raises(ModelOutputError, match="primary_mode_mismatch"):
        parse_edit_payload(raw.replace('"primary_mode": "layout"', '"primary_mode": "topk"'), "layout", parent_source="")


def test_unified_diff_application_replaces_exact_parent_line() -> None:
    parent = "a\nb\nc\n"
    diff = "--- parent_solution.py\n+++ proposed_solution.py\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n"
    assert apply_unified_diff(parent, diff) == "a\nB\nc\n"


def test_unified_diff_rejects_context_mismatch() -> None:
    parent = "a\nx\nc\n"
    diff = "--- parent_solution.py\n+++ proposed_solution.py\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n"
    with pytest.raises(PatchApplyError):
        apply_unified_diff(parent, diff)


def test_unified_diff_applies_exact_context_with_wrong_line_number() -> None:
    parent = "header\na\nb\nc\nfooter\n"
    diff = "--- parent_solution.py\n+++ proposed_solution.py\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c\n"
    assert apply_unified_diff(parent, diff) == "header\na\nB\nc\nfooter\n"


def test_patch_payload_requires_parent_source() -> None:
    raw = (FIXTURES / "claude_edit_cli.json").read_text(encoding="utf-8")
    with pytest.raises(ModelOutputError, match="parent_source_required"):
        parse_edit_payload(raw, "layout")


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


def test_edit_prompt_requests_patch_not_replacement_source() -> None:
    rendered = render_template(
        "mode_edit.txt",
        mode="layout",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine: pass",
    )
    assert "unified_diff" in rendered
    assert "primary_mode" in rendered
    assert "Do not return a complete replacement file" in rendered
    assert "solution_py" not in rendered


def test_replacement_prompt_requests_complete_source() -> None:
    rendered = render_template(
        "mode_edit_replacement.txt",
        mode="layout",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine: pass",
    )
    assert "replacement_file" in rendered
    assert "solution_py as a complete Python file" in rendered


def test_parse_json_object_from_fenced_text() -> None:
    assert parse_json_object("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_parse_json_object_repairs_triple_quoted_string_values() -> None:
    raw = '```json\n{"source": """\ndef f():\n    return 1\n"""}\n```'
    assert parse_json_object(raw) == {"source": "\ndef f():\n    return 1\n"}
