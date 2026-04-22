from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.taxonomy import MODES
from vao.workspaces import create_step_branches


class FakeOpenAICompatibleAdapter(OpenAICompatibleAdapter):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(
            model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct",
            base_url="http://localhost:8000/v1",
            timeout_seconds=1,
        )
        self.payload = payload

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        return json.dumps(self.payload, sort_keys=True), {
            "transport": "openai_compatible",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "input_tokens": 10, "output_tokens": 20},
            "model": self.model_id,
            "elapsed_wall_seconds": 0.01,
        }


def test_openai_compatible_batched_structured_edits_materialize_candidates(tmp_path: Path) -> None:
    parent_source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace" / "solution.py"
    workspace.parent.mkdir(parents=True)
    workspace.write_text(parent_source, encoding="utf-8")
    branch_dirs = create_step_branches(run_dir, 0, workspace, MODES)
    adapter = FakeOpenAICompatibleAdapter(_batch_payload())

    distribution, proposals = adapter.propose_step_batch(_state(workspace, parent_source), branch_dirs)

    assert distribution.top_mode == "indexing"
    assert distribution.parsed_json["transport"] == "openai_compatible"
    assert set(proposals) == set(MODES)
    for mode, proposal in proposals.items():
        assert proposal.declared_mode == mode
        assert proposal.parsed_output_json["edit_protocol"] == "structured_edits"
        assert proposal.parsed_output_json["candidate_generation"] == "batched_structured_edits"
        assert "Qwen smoke" in Path(proposal.file_path).read_text(encoding="utf-8")


def test_openai_compatible_batched_invalid_candidate_becomes_logged_noop(tmp_path: Path) -> None:
    parent_source = Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace" / "solution.py"
    workspace.parent.mkdir(parents=True)
    workspace.write_text(parent_source, encoding="utf-8")
    branch_dirs = create_step_branches(run_dir, 0, workspace, MODES)
    payload = _batch_payload()
    payload["candidates"]["micro"] = {
        "primary_mode": "micro",
        "declared_mode": "micro",
        "edit_format": "structured_edits",
        "rationale": "Invalid candidate that attempts full replacement.",
        "solution_py": parent_source,
        "edits": [{"op": "replace_exact", "old": "missing", "new": "still missing"}],
    }
    adapter = FakeOpenAICompatibleAdapter(payload)

    _, proposals = adapter.propose_step_batch(_state(workspace, parent_source), branch_dirs)

    micro = proposals["micro"]
    assert micro.changed is False
    assert micro.validation_failures == ["candidate_rejected_from_batch"]
    assert any("batch_candidate_invalid" in error for error in micro.errors)
    assert Path(micro.file_path).read_text(encoding="utf-8") == parent_source


def _state(workspace: Path, parent_source: str) -> AgentState:
    return AgentState(
        run_id="qwen_test",
        profile_id="hard_optimization",
        model_id="Qwen/Qwen2.5-Coder-1.5B-Instruct",
        step=0,
        current_solution_path=workspace,
        current_solution_source=parent_source,
        visible_history=[],
        profile_summary={"profile_id": "hard_optimization"},
        residual_steps=1,
        residual_wall_seconds=300.0,
        visibility_regime="top1_only",
        metadata={},
    )


def _batch_payload() -> dict[str, Any]:
    return {
        "mode_probs": {
            "layout": 0.12,
            "indexing": 0.38,
            "topk": 0.14,
            "caching": 0.15,
            "summaries": 0.16,
            "micro": 0.05,
        },
        "mode_ranking": ["indexing", "summaries", "caching", "topk", "layout", "micro"],
        "mode_rationales": {mode: f"{mode} rationale." for mode in MODES},
        "candidates": {mode: _candidate(mode) for mode in MODES},
    }


def _candidate(mode: str) -> dict[str, Any]:
    return {
        "primary_mode": mode,
        "declared_mode": mode,
        "edit_format": "structured_edits",
        "secondary_modes": [],
        "rationale": f"Small {mode} smoke edit.",
        "target_regions": ["CandidateQueryEngine docstring"],
        "edits": [
            {
                "op": "replace_exact",
                "old": '"""Correct list-backed baseline implementation."""',
                "new": f'"""Correct list-backed baseline implementation. Qwen smoke {mode}."""',
            }
        ],
    }
