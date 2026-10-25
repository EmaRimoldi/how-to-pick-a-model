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
        suggested_index = old_start - 1
        if suggested_index < parent_index:
            suggested_index = parent_index
        if suggested_index > len(parent_lines):
            raise PatchApplyError("hunk_starts_beyond_parent")
        diff_index += 1

        old_block: list[str] = []
        new_block: list[str] = []

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
                old_block.append(content)
                new_block.append(content)
            elif prefix == "-":
                old_block.append(content)
            elif prefix == "+":
                new_block.append(content)
            elif prefix in {"-", "+", " "}:
                raise PatchApplyError("unreachable_invalid_prefix")
            else:
                raise PatchApplyError(f"invalid_hunk_line_prefix:{prefix}")
            diff_index += 1

        match_index = _find_hunk_match(parent_lines, old_block, parent_index, suggested_index)
        output.extend(parent_lines[parent_index:match_index])
        output.extend(new_block)
        parent_index = match_index + len(old_block)

    if not saw_hunk:
        raise PatchApplyError("no_hunks_found")

    output.extend(parent_lines[parent_index:])
    trailing_newline = "\n" if parent_source.endswith("\n") else ""
    return "\n".join(output) + trailing_newline


def _find_hunk_match(parent_lines: list[str], old_block: list[str], parent_index: int, suggested_index: int) -> int:
    if not old_block:
        return suggested_index
    if _block_matches(parent_lines, suggested_index, old_block):
        return suggested_index
    matches = [
        index
        for index in range(parent_index, len(parent_lines) - len(old_block) + 1)
        if _block_matches(parent_lines, index, old_block)
    ]
    if not matches:
        expected = old_block[0] if old_block else ""
        actual = parent_lines[suggested_index] if suggested_index < len(parent_lines) else "<eof>"
        raise PatchApplyError(
            "hunk_context_mismatch:"
            f"line={suggested_index + 1}:"
            f"expected={expected!r}:"
            f"actual={actual!r}"
        )
    if len(matches) > 1:
        raise PatchApplyError(f"ambiguous_hunk_context:{matches[:5]}")
    return matches[0]


def _block_matches(parent_lines: list[str], index: int, block: list[str]) -> bool:
    if index < 0 or index + len(block) > len(parent_lines):
        return False
    return parent_lines[index : index + len(block)] == block
