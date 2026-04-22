"""LangGraph direct file-edit workflow for branch-local candidate editing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from vao.agents.claude_parser import ModelOutputError, parse_json_object, validate_candidate_source
from vao.logging_utils import sha256_file
from vao.prompts import shared_canonical_task
from vao.structured_edits import StructuredEditError, apply_structured_edits
from vao.taxonomy import validate_mode


CompletionFn = Callable[[str, dict[str, Any], int], tuple[str, dict[str, Any]]]


class DirectEditState(TypedDict):
    mode: str
    file_path: str
    prompt_context: dict[str, Any]
    max_iterations: int
    max_source_chars: int
    iteration: int
    raw_outputs: list[str]
    parsed_outputs: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    errors: list[str]
    usage: dict[str, Any]
    done: bool
    final_summary: str


class BranchFileEditor:
    """Restricted branch-local file tools.

    The model never receives shell access here. Every tool method operates only
    on the branch's `proposed_solution.py` path.
    """

    def __init__(self, file_path: Path, *, max_source_chars: int = 12000) -> None:
        self.file_path = file_path
        self.max_source_chars = int(max_source_chars)

    def apply_tool_call(self, call: dict[str, Any]) -> dict[str, Any]:
        tool = str(call.get("tool", ""))
        try:
            if tool == "read_file":
                return self._read_file()
            if tool == "validate_file":
                return self._validate_file()
            if tool in {"replace_exact", "delete_exact", "insert_before", "insert_after", "replace_function"}:
                return self._apply_structured_tool(tool, call)
            if tool == "finish":
                return {"tool": tool, "status": "ok", "message": "finished"}
            return {"tool": tool, "status": "error", "error": f"unknown_tool:{tool}"}
        except Exception as exc:  # noqa: BLE001 - tool failures are observations for the graph.
            return {"tool": tool, "status": "error", "error": f"{type(exc).__name__}: {exc}"}

    def _read_file(self) -> dict[str, Any]:
        source = self.file_path.read_text(encoding="utf-8")
        return {
            "tool": "read_file",
            "status": "ok",
            "source": source[: self.max_source_chars],
            "truncated": len(source) > self.max_source_chars,
            "source_hash": sha256_file(self.file_path),
        }

    def _validate_file(self) -> dict[str, Any]:
        source = self.file_path.read_text(encoding="utf-8")
        validation = validate_candidate_source(source)
        return {
            "tool": "validate_file",
            "status": "ok" if validation.get("passed") else "validation_failed",
            "validation": validation,
            "source_hash": sha256_file(self.file_path),
        }

    def _apply_structured_tool(self, tool: str, call: dict[str, Any]) -> dict[str, Any]:
        before = self.file_path.read_text(encoding="utf-8")
        edit = _tool_call_to_structured_edit(tool, call)
        try:
            after = apply_structured_edits(before, [edit])
        except StructuredEditError as exc:
            return {
                "tool": tool,
                "status": "error",
                "error": f"structured_edit_failed:{exc}",
                "source_hash": sha256_file(self.file_path),
            }
        self.file_path.write_text(after, encoding="utf-8")
        validation = validate_candidate_source(after)
        return {
            "tool": tool,
            "status": "ok" if validation.get("passed") else "validation_failed",
            "changed": before != after,
            "source_hash": sha256_file(self.file_path),
            "validation": validation,
        }


def run_direct_file_edit_graph(
    *,
    mode: str,
    file_path: Path,
    profile_summary: dict[str, Any],
    visible_history: list[dict[str, Any]],
    complete: CompletionFn,
    max_iterations: int = 4,
    max_source_chars: int = 12000,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Run a LangGraph loop where the model edits the branch file via tools."""
    validate_mode(mode)
    editor = BranchFileEditor(file_path, max_source_chars=max_source_chars)

    def model_node(graph_state: DirectEditState) -> dict[str, Any]:
        prompt = _render_direct_edit_prompt(graph_state)
        raw, meta = complete(prompt, _direct_edit_schema(), max_tokens)
        raw_outputs = list(graph_state["raw_outputs"]) + [raw]
        parsed_outputs = list(graph_state["parsed_outputs"])
        errors = list(graph_state["errors"])
        try:
            parsed = parse_json_object(raw)
        except ModelOutputError as exc:
            parsed = {"done": True, "summary": "Model output was not parseable JSON.", "tool_calls": []}
            errors.append(f"model_parse_error:{exc}")
        parsed_outputs.append(parsed)
        usage = _merge_usage(graph_state["usage"], meta)
        tool_calls = parsed.get("tool_calls")
        done = bool(parsed.get("done")) or not isinstance(tool_calls, list) or not tool_calls
        return {
            "iteration": graph_state["iteration"] + 1,
            "raw_outputs": raw_outputs,
            "parsed_outputs": parsed_outputs,
            "errors": errors,
            "usage": usage,
            "done": done,
            "final_summary": str(parsed.get("summary", "")),
        }

    def tool_node(graph_state: DirectEditState) -> dict[str, Any]:
        latest = graph_state["parsed_outputs"][-1] if graph_state["parsed_outputs"] else {}
        calls = latest.get("tool_calls") if isinstance(latest, dict) else []
        events = list(graph_state["tool_events"])
        done = bool(latest.get("done")) if isinstance(latest, dict) else True
        if isinstance(calls, list):
            for call in calls[:3]:
                if isinstance(call, dict):
                    event = editor.apply_tool_call(call)
                else:
                    event = {"tool": "", "status": "error", "error": "tool_call_not_object"}
                events.append(event)
                if event.get("tool") == "finish" and event.get("status") == "ok":
                    done = True
        validation = editor._validate_file()
        events.append({"tool": "post_tool_validation", **validation})
        return {"tool_events": events, "done": done}

    def should_continue(graph_state: DirectEditState) -> str:
        if graph_state["done"] or graph_state["iteration"] >= graph_state["max_iterations"]:
            return END
        return "tools"

    def should_loop(graph_state: DirectEditState) -> str:
        if graph_state["done"] or graph_state["iteration"] >= graph_state["max_iterations"]:
            return END
        return "model"

    graph = StateGraph(DirectEditState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", should_continue)
    graph.add_conditional_edges("tools", should_loop)
    app = graph.compile()
    initial: DirectEditState = {
        "mode": mode,
        "file_path": str(file_path),
        "prompt_context": {
            "profile_summary": profile_summary,
            "visible_history": visible_history,
            "current_source": file_path.read_text(encoding="utf-8")[:max_source_chars],
        },
        "max_iterations": max_iterations,
        "max_source_chars": max_source_chars,
        "iteration": 0,
        "raw_outputs": [],
        "parsed_outputs": [],
        "tool_events": [],
        "errors": [],
        "usage": {},
        "done": False,
        "final_summary": "",
    }
    final = app.invoke(initial, {"recursion_limit": max_iterations * 3 + 5})
    final["final_validation"] = editor._validate_file()
    final["final_source_hash"] = sha256_file(file_path)
    final["langgraph_nodes"] = ["model", "tools"]
    return final


def _render_direct_edit_prompt(graph_state: DirectEditState) -> str:
    source = Path(graph_state["file_path"]).read_text(encoding="utf-8")
    tool_events = graph_state["tool_events"][-8:]
    context = graph_state["prompt_context"]
    return f"""{shared_canonical_task()}

BACKEND_OUTPUT_CONTRACT

You are editing one branch-local solution.py directly through tools.

Primary mode for this branch: {graph_state["mode"]}

You may only edit this branch-local file:
{graph_state["file_path"]}

Do not describe a full replacement file. Do not use shell commands. Return JSON
with tool_calls. Each tool call will be executed immediately against this file.

Allowed tools:
- read_file: {{"tool": "read_file"}}
- replace_exact: {{"tool": "replace_exact", "old": "exact existing text", "new": "replacement text"}}
- delete_exact: {{"tool": "delete_exact", "text": "exact existing text"}}
- insert_before: {{"tool": "insert_before", "anchor": "exact existing text", "text": "inserted text"}}
- insert_after: {{"tool": "insert_after", "anchor": "exact existing text", "text": "inserted text"}}
- replace_function: {{"tool": "replace_function", "function": "function_name", "source": "complete replacement function with exact indentation"}}
- validate_file: {{"tool": "validate_file"}}
- finish: {{"tool": "finish"}}

Return JSON shaped as:
{{"summary": "short summary", "done": false, "tool_calls": [{{...}}]}}

Use at most 3 tool calls per turn. When the file is valid and the branch edit is
complete, call validate_file and finish or set done=true with no tool_calls.

Profile summary:
{json.dumps(context["profile_summary"], sort_keys=True)}

Visible history:
{json.dumps(context["visible_history"], sort_keys=True)}

Recent tool events:
{json.dumps(tool_events, sort_keys=True)}

Current branch-local solution.py:
```python
{source[: graph_state["max_source_chars"]]}
```
"""


def _direct_edit_schema() -> dict[str, Any]:
    tool_call = {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "tool": {
                "type": "string",
                "enum": [
                    "read_file",
                    "replace_exact",
                    "delete_exact",
                    "insert_before",
                    "insert_after",
                    "replace_function",
                    "validate_file",
                    "finish",
                ],
            }
        },
        "required": ["tool"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "done": {"type": "boolean"},
            "tool_calls": {"type": "array", "items": tool_call, "maxItems": 3},
        },
        "required": ["summary", "done", "tool_calls"],
    }


def _tool_call_to_structured_edit(tool: str, call: dict[str, Any]) -> dict[str, Any]:
    if tool == "replace_exact":
        return {"op": tool, "old": str(call.get("old", "")), "new": str(call.get("new", ""))}
    if tool == "delete_exact":
        return {"op": tool, "text": str(call.get("text", ""))}
    if tool == "insert_before":
        return {"op": tool, "anchor": str(call.get("anchor", "")), "text": str(call.get("text", ""))}
    if tool == "insert_after":
        return {"op": tool, "anchor": str(call.get("anchor", "")), "text": str(call.get("text", ""))}
    if tool == "replace_function":
        return {"op": tool, "function": str(call.get("function", "")), "source": str(call.get("source", ""))}
    raise ValueError(f"not_an_edit_tool:{tool}")


def _merge_usage(current: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    usage = dict(current)
    raw_usage = meta.get("usage") if isinstance(meta, dict) else None
    if isinstance(raw_usage, dict):
        for key, value in raw_usage.items():
            if isinstance(value, (int, float)):
                usage[key] = usage.get(key, 0) + value
    if isinstance(meta, dict) and meta.get("cost_usd") is not None:
        usage["cost_usd"] = usage.get("cost_usd", 0.0) + float(meta["cost_usd"])
    return usage
