"""OpenAI-compatible direct file-edit adapter using LangGraph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vao.agents.base import AgentState
from vao.agents.direct_file_edit import run_direct_file_edit_graph
from vao.agents.openai_compatible_adapter import OpenAICompatibleAdapter
from vao.logging_utils import sha256_file, sha256_text
from vao.schemas import CandidateProposal
from vao.taxonomy import MODES, validate_mode


class OpenAICompatibleDirectEditAdapter(OpenAICompatibleAdapter):
    """Let a model directly edit branch-local `proposed_solution.py` via tools.

    This backend preserves C(a) branch isolation because every tool is bound to a
    single branch directory. The model can iteratively call file-edit tools, but
    it never gets shell access and cannot read or write other branches.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str,
        *,
        max_direct_edit_iterations: int = 4,
        max_direct_edit_tokens: int = 2048,
        max_source_chars: int = 12000,
        edit_protocol: str = "direct_file_tools",
        **kwargs: object,
    ) -> None:
        if edit_protocol != "direct_file_tools":
            raise ValueError(f"unsupported direct edit protocol: {edit_protocol}")
        super().__init__(model_id=model_id, edit_protocol="structured_edits", **kwargs)
        self.edit_protocol = "direct_file_tools"
        self.max_direct_edit_iterations = int(max_direct_edit_iterations)
        self.max_direct_edit_tokens = int(max_direct_edit_tokens)
        self.max_source_chars = int(max_source_chars)

    def propose_step_batch(self, state: AgentState, branch_dirs: dict[str, Path]) -> Any:
        raise ValueError("direct file editing is per-mode only; set candidate_generation: per_mode")

    def propose_edit_for_mode(self, state: AgentState, mode: str, branch_dir: Path) -> CandidateProposal:
        validate_mode(mode)
        parent_path = branch_dir / "parent_solution.py"
        proposed_path = branch_dir / "proposed_solution.py"
        before_hash = sha256_file(proposed_path)

        def complete(prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
            return self._complete(prompt, schema, max_tokens)

        graph_result = run_direct_file_edit_graph(
            mode=mode,
            file_path=proposed_path,
            profile_summary=state.profile_summary,
            visible_history=state.visible_history,
            complete=complete,
            max_iterations=self.max_direct_edit_iterations,
            max_source_chars=self.max_source_chars,
            max_tokens=self.max_direct_edit_tokens,
        )
        trace_path = branch_dir / "direct_edit_trace.json"
        trace_path.write_text(json.dumps(graph_result, indent=2, sort_keys=True), encoding="utf-8")
        final_validation = graph_result.get("final_validation", {})
        usage = graph_result.get("usage") if isinstance(graph_result.get("usage"), dict) else {}
        changed = before_hash != sha256_file(proposed_path)
        validation_failures = []
        if isinstance(final_validation, dict) and not final_validation.get("validation", {}).get("passed", True):
            validation_failures.extend(str(item) for item in final_validation.get("validation", {}).get("errors", []))
        return CandidateProposal(
            branch_index=MODES.index(mode),
            primary_mode=mode,
            secondary_modes=[],
            declared_mode=mode,
            source_hash=sha256_file(proposed_path),
            source_parent_hash=sha256_file(parent_path),
            file_path=str(proposed_path),
            raw_output_text="\n\n".join(str(item) for item in graph_result.get("raw_outputs", [])),
            parsed_output_json={
                "edit_protocol": "direct_file_tools",
                "candidate_generation": "langgraph_direct_file_edit",
                "direct_edit_trace_path": str(trace_path),
                "direct_edit_iterations": graph_result.get("iteration"),
                "direct_edit_done": graph_result.get("done"),
                "direct_edit_summary": graph_result.get("final_summary"),
                "direct_edit_tool_events": graph_result.get("tool_events", []),
                "direct_edit_errors": graph_result.get("errors", []),
                "source_validation": final_validation,
                "usage": usage,
                "model": self.model_id,
                "transport": "openai_compatible_direct_edit",
            },
            prompt_hash=sha256_text(
                json.dumps(
                    {
                        "run_id": state.run_id,
                        "step": state.step,
                        "profile_id": state.profile_id,
                        "mode": mode,
                        "parent_hash": sha256_file(parent_path),
                        "edit_protocol": "direct_file_tools",
                    },
                    sort_keys=True,
                )
            ),
            changed=changed,
            errors=[str(item) for item in graph_result.get("errors", [])],
            validation_failures=validation_failures,
            usage=usage,
            model=self.model_id,
            transport="openai_compatible_direct_edit",
        )
