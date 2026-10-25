"""Structured source-edit application for compact model edits."""

from __future__ import annotations

import ast
from typing import Any


class StructuredEditError(ValueError):
    """Raised when a structured edit cannot be applied exactly."""


def apply_structured_edits(parent_source: str, edits: list[dict[str, Any]]) -> str:
    """Apply a sequence of exact structured edits to Python source.

    Supported operations are intentionally small and auditable:

    - replace_exact: replace an exact text span once.
    - delete_exact: delete an exact text span once.
    - insert_before / insert_after: insert text around an exact anchor once.
    - replace_function: replace a top-level or class method function block.

    The operation fails if the target is missing or ambiguous. This keeps the
    model from silently editing the wrong branch-local file.
    """
    if not isinstance(edits, list) or not edits:
        raise StructuredEditError("edits_missing_or_empty")
    source = parent_source
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise StructuredEditError(f"edit_{index}_not_object")
        op = str(edit.get("op", ""))
        if op == "replace_exact":
            source = _replace_exact(source, str(edit.get("old", "")), str(edit.get("new", "")), index)
        elif op == "delete_exact":
            source = _replace_exact(source, str(edit.get("text", "")), "", index)
        elif op == "insert_before":
            source = _insert(source, str(edit.get("anchor", "")), str(edit.get("text", "")), before=True, index=index)
        elif op == "insert_after":
            source = _insert(source, str(edit.get("anchor", "")), str(edit.get("text", "")), before=False, index=index)
        elif op == "replace_function":
            source = _replace_function(source, str(edit.get("function", "")), str(edit.get("source", "")), index)
        else:
            raise StructuredEditError(f"edit_{index}_unknown_op:{op}")
    return _preserve_final_newline(parent_source, source)


def _replace_exact(source: str, old: str, new: str, index: int) -> str:
    if not old:
        raise StructuredEditError(f"edit_{index}_empty_old_text")
    count = source.count(old)
    if count == 0:
        raise StructuredEditError(f"edit_{index}_old_text_not_found")
    if count > 1:
        raise StructuredEditError(f"edit_{index}_old_text_ambiguous:{count}")
    return source.replace(old, new, 1)


def _insert(source: str, anchor: str, text: str, *, before: bool, index: int) -> str:
    if not anchor:
        raise StructuredEditError(f"edit_{index}_empty_anchor")
    if not text:
        raise StructuredEditError(f"edit_{index}_empty_insert_text")
    count = source.count(anchor)
    if count == 0:
        raise StructuredEditError(f"edit_{index}_anchor_not_found")
    if count > 1:
        raise StructuredEditError(f"edit_{index}_anchor_ambiguous:{count}")
    position = source.index(anchor)
    if before:
        return source[:position] + text + source[position:]
    position += len(anchor)
    return source[:position] + text + source[position:]


def _replace_function(source: str, function_name: str, replacement: str, index: int) -> str:
    if not function_name:
        raise StructuredEditError(f"edit_{index}_missing_function")
    if not replacement.strip():
        raise StructuredEditError(f"edit_{index}_empty_function_source")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise StructuredEditError(f"parent_syntax_error:{exc}") from exc
    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            candidates.append(node)
    if not candidates:
        raise StructuredEditError(f"edit_{index}_function_not_found:{function_name}")
    if len(candidates) > 1:
        raise StructuredEditError(f"edit_{index}_function_ambiguous:{function_name}:{len(candidates)}")
    node = candidates[0]
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    lines = source.splitlines()
    replacement_lines = replacement.rstrip("\n").splitlines()
    if not replacement_lines:
        raise StructuredEditError(f"edit_{index}_empty_function_source")
    expected_indent = _leading_spaces(lines[start])
    actual_indent = _leading_spaces(replacement_lines[0])
    if actual_indent != expected_indent:
        raise StructuredEditError(
            f"edit_{index}_function_indent_mismatch:expected={expected_indent}:actual={actual_indent}"
        )
    new_lines = lines[:start] + replacement_lines + lines[end:]
    return "\n".join(new_lines) + ("\n" if source.endswith("\n") else "")


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _preserve_final_newline(parent_source: str, source: str) -> str:
    if parent_source.endswith("\n") and not source.endswith("\n"):
        return source + "\n"
    if not parent_source.endswith("\n") and source.endswith("\n"):
        return source.rstrip("\n")
    return source
