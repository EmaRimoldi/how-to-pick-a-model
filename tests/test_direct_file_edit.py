from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.agents.direct_file_edit import run_direct_file_edit_graph
from vao.agents.openai_direct_edit_adapter import OpenAICompatibleDirectEditAdapter
from vao.taxonomy import MODES
from vao.workspaces import create_step_branches


def test_langgraph_direct_file_edit_modifies_branch_local_file(tmp_path: Path) -> None:
    solution = tmp_path / "proposed_solution.py"
    solution.write_text(_parent_source(), encoding="utf-8")
    calls = [
        {
            "summary": "Make a direct line edit.",
            "done": False,
            "tool_calls": [
                {
                    "tool": "replace_exact",
                    "old": '"""Correct list-backed baseline implementation."""',
                    "new": '"""Direct-edit smoke marker."""',
                },
                {"tool": "validate_file"},
            ],
        },
        {"summary": "Finished.", "done": True, "tool_calls": []},
    ]

    def complete(prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        return json.dumps(calls.pop(0)), {"usage": {"input_tokens": 1, "output_tokens": 2}}

    result = run_direct_file_edit_graph(
        mode="micro",
        file_path=solution,
        profile_summary={"profile_id": "hard_optimization"},
        visible_history=[],
        complete=complete,
        max_iterations=3,
    )

    assert "Direct-edit smoke marker" in solution.read_text(encoding="utf-8")
    assert result["langgraph_nodes"] == ["model", "tools"]
    assert result["final_validation"]["validation"]["passed"] is True
    assert result["usage"]["input_tokens"] == 2


def test_direct_edit_adapter_returns_candidate_proposal(tmp_path: Path) -> None:
    parent = _parent_source()
    run_dir = tmp_path / "run"
    workspace = run_dir / "workspace" / "solution.py"
    workspace.parent.mkdir(parents=True)
    workspace.write_text(parent, encoding="utf-8")
    branch_dirs = create_step_branches(run_dir, 0, workspace, MODES)

    class FakeDirectAdapter(OpenAICompatibleDirectEditAdapter):
        def __init__(self) -> None:
            super().__init__(
                model_id="fake-qwen-direct",
                base_url="http://localhost:8000/v1",
                max_direct_edit_iterations=2,
            )
            self.calls = [
                {
                    "summary": "Directly edit the branch file.",
                    "done": False,
                    "tool_calls": [
                        {
                            "tool": "replace_exact",
                            "old": '"""Correct list-backed baseline implementation."""',
                            "new": '"""Direct adapter smoke marker."""',
                        }
                    ],
                },
                {"summary": "Finished.", "done": True, "tool_calls": []},
            ]

        def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
            return json.dumps(self.calls.pop(0)), {"usage": {"input_tokens": 3, "output_tokens": 4}}

    state = AgentState(
        run_id="direct_adapter_test",
        profile_id="hard_optimization",
        model_id="fake-qwen-direct",
        step=0,
        current_solution_path=workspace,
        current_solution_source=parent,
        visible_history=[],
        profile_summary={"profile_id": "hard_optimization"},
        residual_steps=1,
        residual_wall_seconds=60.0,
        visibility_regime="top1_only",
        metadata={},
    )
    proposal = FakeDirectAdapter().propose_edit_for_mode(state, "micro", branch_dirs["micro"])

    assert proposal.changed is True
    assert proposal.parsed_output_json["edit_protocol"] == "direct_file_tools"
    assert proposal.parsed_output_json["candidate_generation"] == "langgraph_direct_file_edit"
    assert Path(proposal.parsed_output_json["direct_edit_trace_path"]).exists()
    assert "Direct adapter smoke marker" in Path(proposal.file_path).read_text(encoding="utf-8")


def _parent_source() -> str:
    return Path("benchmarks/stateful_query_engine/solution_template.py").read_text(encoding="utf-8")
