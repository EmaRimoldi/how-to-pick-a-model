"""Patch application utilities for model-produced source edits."""

from __future__ import annotations

import re


class PatchApplyError(ValueError):
    """Raised when a model-produced patch cannot be applied exactly."""


_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def apply_unified_diff(parent_source: str, diff_text: str) -> str:
    """Apply a standard unified diff to a source string.

    The implementation is intentionally strict: context and removed lines must
    match the parent exactly. This keeps experiment branches reproducible and
    prevents a malformed model edit from being silently interpreted.
    """
    if not isinstance(diff_text, str) or not diff_text.strip():
        raise PatchApplyError("empty_unified_diff")

    diff_lines = diff_text.splitlines()
    parent_lines = parent_source.splitlines()
    output: list[str] = []
    parent_index = 0
    diff_index = 0
    saw_hunk = False

    while diff_index < len(diff_lines):
        line = diff_lines[diff_index]
        if not line.startswith("@@"):
            diff_index += 1
            continue

        match = _HUNK_RE.match(line)
        if not match:
            raise PatchApplyError(f"invalid_hunk_header:{line}")
        saw_hunk = True
        old_start = int(match.group("old_start"))
        hunk_parent_index = old_start - 1
        if hunk_parent_index < parent_index:
            raise PatchApplyError("overlapping_or_out_of_order_hunk")
        if hunk_parent_index > len(parent_lines):
            raise PatchApplyError("hunk_starts_beyond_parent")

        output.extend(parent_lines[parent_index:hunk_parent_index])
        parent_index = hunk_parent_index
        diff_index += 1

        while diff_index < len(diff_lines) and not diff_lines[diff_index].startswith("@@"):
            hunk_line = diff_lines[diff_index]
            if hunk_line == r"\ No newline at end of file":
                diff_index += 1
                continue
            if not hunk_line:
                raise PatchApplyError("invalid_empty_hunk_line")
            prefix = hunk_line[0]
            content = hunk_line[1:]
            if prefix == " ":
                _require_parent_line(parent_lines, parent_index, content)
                output.append(content)
                parent_index += 1
            elif prefix == "-":
                _require_parent_line(parent_lines, parent_index, content)
                parent_index += 1
            elif prefix == "+":
                output.append(content)
            elif prefix in {"-", "+", " "}:
                raise PatchApplyError("unreachable_invalid_prefix")
            else:
                raise PatchApplyError(f"invalid_hunk_line_prefix:{prefix}")
            diff_index += 1

    if not saw_hunk:
        raise PatchApplyError("no_hunks_found")

    output.extend(parent_lines[parent_index:])
    trailing_newline = "\n" if parent_source.endswith("\n") else ""
    return "\n".join(output) + trailing_newline


def _require_parent_line(parent_lines: list[str], index: int, expected: str) -> None:
    if index >= len(parent_lines):
        raise PatchApplyError("hunk_consumes_past_parent")
    actual = parent_lines[index]
    if actual != expected:
        raise PatchApplyError(
            "hunk_context_mismatch:"
            f"line={index + 1}:"
            f"expected={expected!r}:"
            f"actual={actual!r}"
        )
