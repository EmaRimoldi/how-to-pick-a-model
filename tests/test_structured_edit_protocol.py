from __future__ import annotations

import json
from pathlib import Path

import pytest

from vao.agents.claude_parser import ModelOutputError, parse_structured_edit_payload
from vao.prompts import render_template
from vao.structured_edits import StructuredEditError, apply_structured_edits


def test_replace_exact_structured_edit() -> None:
    parent = "class CandidateQueryEngine:\n    def get(self, key):\n        return None\n"
    edited = apply_structured_edits(
        parent,
        [{"op": "replace_exact", "old": "        return None", "new": "        return 1"}],
    )
    assert "return 1" in edited


def test_replace_function_structured_edit_validates_candidate() -> None:
    parent = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    new_get = """    def get(self, key: int) -> int | None:
        key = int(key)
        for existing_key, value in self._items:
            if existing_key == key:
                return value
        return None
"""
    raw = json.dumps(
        {
            "primary_mode": "micro",
            "declared_mode": "micro",
            "edit_format": "structured_edits",
            "rationale": "Keep get behavior identical while exercising structured replacement.",
            "edits": [{"op": "replace_function", "function": "get", "source": new_get}],
        }
    )
    parsed = parse_structured_edit_payload(raw, "micro", parent_source=parent)
    assert parsed["structured_edit_apply_status"] == "passed"
    assert "class CandidateQueryEngine" in parsed["solution_py"]
    assert "solution_py" not in json.loads(raw)


def test_structured_parser_repairs_banned_list_remove() -> None:
    parent = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    new_delete = """    def delete(self, key: int) -> None:
        key = int(key)
        for item in list(self._items):
            if item[0] == key:
                self._items.remove(item)
                return None
        return None
"""
    raw = json.dumps(
        {
            "primary_mode": "layout",
            "declared_mode": "layout",
            "edit_format": "structured_edits",
            "rationale": "Exercise deterministic list.remove repair.",
            "edits": [{"op": "replace_function", "function": "delete", "source": new_delete}],
        }
    )
    parsed = parse_structured_edit_payload(raw, "layout", parent_source=parent)
    assert parsed["source_repair_status"] == "applied"
    assert parsed["source_repairs"] == ["list_remove_rewritten_to_comprehension"]
    assert ".remove(" not in parsed["solution_py"]
    assert "__vao_keep_item_0" in parsed["solution_py"]


def test_structured_edit_rejects_ambiguous_exact_match() -> None:
    with pytest.raises(StructuredEditError, match="ambiguous"):
        apply_structured_edits("x = 1\nx = 1\n", [{"op": "replace_exact", "old": "x = 1", "new": "x = 2"}])


def test_structured_parser_rejects_replacement_file() -> None:
    parent = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    raw = json.dumps(
        {
            "primary_mode": "micro",
            "declared_mode": "micro",
            "edit_format": "structured_edits",
            "rationale": "Invalid full replacement.",
            "edits": [{"op": "replace_exact", "old": "return rows[:k]", "new": "return rows[:k]"}],
            "solution_py": parent,
        }
    )
    with pytest.raises(ModelOutputError, match="replacement_file_output_not_allowed"):
        parse_structured_edit_payload(raw, "micro", parent_source=parent)


def test_structured_prompt_forbids_solution_py() -> None:
    rendered = render_template(
        "mode_edit_structured.txt",
        mode="micro",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine:\n    pass\n",
    )
    assert "structured_edits" in rendered
    assert "Do not return solution_py" in rendered
    assert "complete replacement file" in rendered
    assert "Do not call banned attributes" in rendered
    assert "(-value, key)" in rendered
    assert "Never use `keys.remove(key)`" in rendered


def test_batch_structured_prompt_requests_one_candidate_per_mode() -> None:
    rendered = render_template(
        "step_batch_structured.txt",
        profile_summary="{}",
        visible_history="[]",
        current_solution_source="class CandidateQueryEngine:\n    pass\n",
    )
    assert "mode_probs" in rendered
    assert "Exactly one compact structured edit candidate for each mode" in rendered
    assert "Do not return solution_py" in rendered
    assert "Do not call banned attributes" in rendered
    assert "(-value, key)" in rendered
    assert "Never use `keys.remove(key)`" in rendered
    for mode in ["layout", "indexing", "topk", "caching", "summaries", "micro"]:
        assert mode in rendered
