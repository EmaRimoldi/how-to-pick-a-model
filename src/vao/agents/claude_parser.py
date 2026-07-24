"""Parsing and validation helpers for Claude/Anthropic backend outputs."""

from __future__ import annotations

import ast
import copy
import json
import re
import textwrap
from typing import Any
from typing import Callable

from pydantic import ValidationError

from vao.patches import PatchApplyError, apply_unified_diff
from vao.schemas import ModeDistribution
from vao.structured_edits import StructuredEditError, apply_structured_edits
from vao.taxonomy import MODES, MODE_SET, normalize_mode_probs, validate_mode
from vao.verifier import validate_source


class ModelOutputError(ValueError):
    """Raised when a model response cannot be repaired into the required form."""


def parse_json_object(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object from raw model text or Claude CLI result JSON."""
    stripped = raw_text.strip()
    if not stripped:
        raise ModelOutputError("empty_model_output")
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        if isinstance(parsed.get("structured_output"), dict):
            return parsed["structured_output"]
        if _looks_like_protocol_object(parsed):
            return parsed
        result = parsed.get("result")
        if isinstance(result, str):
            try:
                return parse_json_object(result)
            except ModelOutputError:
                pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced:
        return _loads_object(fenced.group(1))
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return _loads_object(stripped[start : end + 1])
    raise ModelOutputError("no_json_object_found")


def repair_distribution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Apply deterministic repairs before Pydantic validation."""
    failures: list[str] = []
    repaired = dict(payload)
    probs = repaired.get("mode_probs")
    if not isinstance(probs, dict):
        raise ModelOutputError("mode_probs_missing_or_not_object")
    repaired_probs: dict[str, float] = {}
    for mode in MODES:
        if mode not in probs:
            failures.append(f"missing_mode_prob:{mode}")
            repaired_probs[mode] = 0.0
            continue
        try:
            repaired_probs[mode] = float(probs[mode])
        except (TypeError, ValueError) as exc:
            raise ModelOutputError(f"non_numeric_probability:{mode}") from exc
    extra = sorted(set(probs) - MODE_SET)
    if extra:
        failures.append(f"extra_mode_probs:{extra}")
    if sum(max(0.0, value) for value in repaired_probs.values()) <= 0:
        repaired_probs = {mode: 1.0 for mode in MODES}
        failures.append("zero_probability_mass_repaired_to_uniform")
    repaired["mode_probs"] = normalize_mode_probs(repaired_probs)

    ranking = repaired.get("mode_ranking")
    if not isinstance(ranking, list):
        ranking = []
        failures.append("mode_ranking_missing_or_not_list")
    filtered = [str(mode) for mode in ranking if mode in MODE_SET]
    for mode in MODES:
        if mode not in filtered:
            filtered.append(mode)
            failures.append(f"mode_ranking_missing_mode:{mode}")
    repaired["mode_ranking"] = filtered[: len(MODES)]

    rationales = repaired.get("mode_rationales")
    if not isinstance(rationales, dict):
        rationales = {}
        failures.append("mode_rationales_missing_or_not_object")
    repaired["mode_rationales"] = {mode: str(rationales.get(mode, "")) for mode in MODES}
    return repaired, failures


def parse_mode_distribution(raw_text: str) -> ModeDistribution:
    payload = parse_json_object(raw_text)
    repaired, failures = repair_distribution_payload(payload)
    try:
        return ModeDistribution(
            mode_probs=repaired["mode_probs"],
            mode_ranking=repaired["mode_ranking"],
            mode_rationales=repaired["mode_rationales"],
            raw_text=raw_text,
            parsed_json=repaired,
            validation_failures=failures,
        )
    except ValidationError as exc:
        raise ModelOutputError(str(exc)) from exc


def parse_edit_payload(
    raw_text: str,
    expected_mode: str,
    parent_source: str | None = None,
    *,
    source_validator: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_mode(expected_mode)
    payload = parse_json_object(raw_text)
    primary = payload.get("primary_mode")
    if primary != expected_mode:
        raise ModelOutputError(f"primary_mode_mismatch:{primary!r}!={expected_mode!r}")
    declared = payload.get("declared_mode")
    if declared != expected_mode:
        raise ModelOutputError(f"declared_mode_mismatch:{declared!r}!={expected_mode!r}")
    if payload.get("edit_format") != "unified_diff":
        raise ModelOutputError(f"edit_format_mismatch:{payload.get('edit_format')!r}")
    source = _materialize_candidate_source(payload, parent_source)
    validation = validate_candidate_source(source, source_validator=source_validator)
    if not validation["passed"]:
        raise ModelOutputError("candidate_source_invalid:" + ";".join(validation["errors"]))
    return {
        **payload,
        "solution_py": source,
        "patch_parse_status": "passed",
        "patch_apply_status": "passed",
        "source_validation": validation,
        "source_validation_status": "passed",
    }


def parse_structured_edit_payload(
    raw_text: str,
    expected_mode: str,
    parent_source: str | None = None,
    *,
    source_validator: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_mode(expected_mode)
    if parent_source is None:
        raise ModelOutputError("parent_source_required_for_structured_edits")
    payload = parse_json_object(raw_text)
    primary = payload.get("primary_mode")
    if primary != expected_mode:
        raise ModelOutputError(f"primary_mode_mismatch:{primary!r}!={expected_mode!r}")
    declared = payload.get("declared_mode")
    if declared != expected_mode:
        raise ModelOutputError(f"declared_mode_mismatch:{declared!r}!={expected_mode!r}")
    if payload.get("edit_format") != "structured_edits":
        raise ModelOutputError(f"edit_format_mismatch:{payload.get('edit_format')!r}")
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ModelOutputError("structured_edits_missing_or_empty")
    if isinstance(payload.get("solution_py"), str):
        raise ModelOutputError("replacement_file_output_not_allowed")
    edits, edit_repairs = _repair_structured_edits_if_safe(parent_source, edits)
    try:
        source = apply_structured_edits(parent_source, edits)
    except StructuredEditError as exc:
        raise ModelOutputError(f"structured_edit_apply_failed:{exc}") from exc
    validation = validate_candidate_source(source, source_validator=source_validator)
    source, validation, source_repairs = _repair_candidate_source_if_safe(
        source,
        validation,
        source_validator=source_validator,
    )
    if not validation["passed"]:
        raise ModelOutputError("candidate_source_invalid:" + ";".join(validation["errors"]))
    return {
        **payload,
        "solution_py": source,
        "patch_parse_status": "not_applicable_structured",
        "patch_apply_status": "not_applicable_structured",
        "structured_edit_parse_status": "passed",
        "structured_edit_apply_status": "passed",
        "source_validation": validation,
        "source_validation_status": "passed",
        "source_repairs": source_repairs,
        "source_repair_status": "applied" if source_repairs else "not_needed",
        "edit_repairs": edit_repairs,
        "edit_repair_status": "applied" if edit_repairs else "not_needed",
    }


def parse_replacement_payload(
    raw_text: str,
    expected_mode: str,
    *,
    source_validator: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_mode(expected_mode)
    payload = parse_json_object(raw_text)
    primary = payload.get("primary_mode")
    if primary != expected_mode:
        raise ModelOutputError(f"primary_mode_mismatch:{primary!r}!={expected_mode!r}")
    declared = payload.get("declared_mode")
    if declared != expected_mode:
        raise ModelOutputError(f"declared_mode_mismatch:{declared!r}!={expected_mode!r}")
    if payload.get("edit_format") != "replacement_file":
        raise ModelOutputError(f"edit_format_mismatch:{payload.get('edit_format')!r}")
    source = payload.get("solution_py")
    if not isinstance(source, str) or not source.strip():
        raise ModelOutputError("solution_py_missing_or_empty")
    validation = validate_candidate_source(source, source_validator=source_validator)
    if not validation["passed"]:
        raise ModelOutputError("candidate_source_invalid:" + ";".join(validation["errors"]))
    return {
        **payload,
        "source_validation": validation,
        "source_validation_status": "passed",
        "patch_parse_status": "not_applicable_replacement",
        "patch_apply_status": "not_applicable_replacement",
    }


def validate_candidate_source(
    source: str,
    *,
    source_validator: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if source_validator is not None:
        return source_validator(source)
    errors: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"passed": False, "errors": [f"SyntaxError: {exc}"]}
    has_candidate = any(isinstance(node, ast.ClassDef) and node.name == "CandidateQueryEngine" for node in tree.body)
    if not has_candidate:
        errors.append("missing CandidateQueryEngine class")
    safety = validate_source(source)
    if not safety.get("passed"):
        errors.extend(str(item) for item in safety.get("errors", []))
    return {"passed": not errors, "errors": sorted(set(errors)), "safety": safety}


def _repair_structured_edits_if_safe(
    parent_source: str,
    edits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    repaired = copy.deepcopy(edits)
    repairs: list[str] = []
    function_indents = _function_indents(parent_source)
    for edit in repaired:
        if not isinstance(edit, dict) or edit.get("op") != "replace_function":
            continue
        function_name = str(edit.get("function", ""))
        source = edit.get("source")
        if not function_name or not isinstance(source, str):
            continue
        expected_indent = function_indents.get(function_name)
        if expected_indent is None or expected_indent == 0:
            continue
        lines = source.strip("\n").splitlines()
        if not lines:
            continue
        first_nonempty = next((line for line in lines if line.strip()), "")
        if first_nonempty.startswith("class "):
            extracted = _extract_function_source_from_class_blob(source, function_name)
            if extracted is None:
                continue
            reindented = _reindent_function_source(extracted, expected_indent)
            if reindented is None:
                continue
            edit["source"] = reindented
            repairs.append(f"replace_function_extracted_from_class_source:{function_name}")
            continue
        if not first_nonempty.startswith("def ") and not first_nonempty.startswith("async def "):
            continue
        reindented = _reindent_function_source(source, expected_indent)
        if reindented is None:
            continue
        edit["source"] = reindented
        repairs.append(f"replace_function_auto_indented:{function_name}:{expected_indent}")
    return repaired, repairs


def _extract_function_source_from_class_blob(source: str, function_name: str) -> str | None:
    """Extract a method body when a small model pasted a whole class for replace_function."""
    try:
        dedented = textwrap.dedent(source.strip("\n"))
        tree = ast.parse(dedented)
    except SyntaxError:
        return None
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
    ]
    if len(matches) != 1:
        return None
    segment = ast.get_source_segment(dedented, matches[0])
    if not segment or not segment.strip():
        return None
    return segment.rstrip("\n")


def _reindent_function_source(source: str, expected_indent: int) -> str | None:
    lines = source.strip("\n").splitlines()
    if not lines:
        return None
    first_nonempty = next((line for line in lines if line.strip()), "")
    if not first_nonempty.startswith("def ") and not first_nonempty.startswith("async def "):
        return None
    actual_indent = len(first_nonempty) - len(first_nonempty.lstrip(" "))
    if actual_indent == expected_indent:
        return "\n".join(lines)
    prefix = " " * expected_indent
    reindented: list[str] = []
    for line in lines:
        if not line.strip():
            reindented.append(line)
        elif len(line) >= actual_indent:
            reindented.append(prefix + line[actual_indent:])
        else:
            return None
    return "\n".join(reindented)


def _function_indents(source: str) -> dict[str, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    lines = source.splitlines()
    indents: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line = lines[node.lineno - 1] if 0 <= node.lineno - 1 < len(lines) else ""
        indents.setdefault(node.name, len(line) - len(line.lstrip(" ")))
    return indents


def _repair_candidate_source_if_safe(
    source: str,
    validation: dict[str, Any],
    *,
    source_validator: Callable[[str], dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any], list[str]]:
    """Apply narrow deterministic repairs for over-broad safety rejections.

    The benchmark safety screen bans every `.remove(...)` attribute call to
    avoid filesystem-style remove operations. Model-generated data-structure
    code often uses `list.remove`, especially for sorted-key deletion. Rather
    than silently accepting the banned call, rewrite simple statement-level
    `container.remove(value)` calls into an assignment that rebuilds the list
    without the value, then validate the repaired full source again.
    """
    if validation.get("passed"):
        return source, validation, []
    errors = {str(error) for error in validation.get("errors", [])}
    if errors != {"banned attribute call: remove"}:
        return source, validation, []
    try:
        tree = ast.parse(source)
        rewriter = _ListRemoveRewriter()
        repaired_tree = rewriter.visit(tree)
        ast.fix_missing_locations(repaired_tree)
        repaired_source = ast.unparse(repaired_tree) + "\n"
    except Exception:  # noqa: BLE001 - failed repair should leave original failure intact.
        return source, validation, []
    if rewriter.rewrite_count == 0 or repaired_source == source:
        return source, validation, []
    repaired_validation = validate_candidate_source(repaired_source, source_validator=source_validator)
    if not repaired_validation.get("passed"):
        return source, validation, []
    return repaired_source, repaired_validation, ["list_remove_rewritten_to_comprehension"]


class _ListRemoveRewriter(ast.NodeTransformer):
    def __init__(self) -> None:
        self.rewrite_count = 0

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        visited = self.generic_visit(node)
        if not isinstance(visited, ast.Expr):
            return visited
        call = visited.value
        if (
            not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Attribute)
            or call.func.attr != "remove"
            or len(call.args) != 1
            or call.keywords
            or not _is_assignable_container(call.func.value)
        ):
            return visited
        item_name = f"__vao_keep_item_{self.rewrite_count}"
        self.rewrite_count += 1
        target = _with_store_context(copy.deepcopy(call.func.value))
        iterator = copy.deepcopy(call.func.value)
        removed_value = copy.deepcopy(call.args[0])
        comprehension = ast.ListComp(
            elt=ast.Name(id=item_name, ctx=ast.Load()),
            generators=[
                ast.comprehension(
                    target=ast.Name(id=item_name, ctx=ast.Store()),
                    iter=iterator,
                    ifs=[
                        ast.Compare(
                            left=ast.Name(id=item_name, ctx=ast.Load()),
                            ops=[ast.NotEq()],
                            comparators=[removed_value],
                        )
                    ],
                    is_async=0,
                )
            ],
        )
        return ast.copy_location(ast.Assign(targets=[target], value=comprehension), visited)


def _is_assignable_container(node: ast.AST) -> bool:
    return isinstance(node, (ast.Name, ast.Attribute, ast.Subscript))


def _with_store_context(node: ast.AST) -> ast.AST:
    if isinstance(node, ast.Name):
        node.ctx = ast.Store()
    elif isinstance(node, ast.Attribute):
        node.ctx = ast.Store()
    elif isinstance(node, ast.Subscript):
        node.ctx = ast.Store()
    return node


def _looks_like_protocol_object(parsed: dict[str, Any]) -> bool:
    return (
        "mode_probs" in parsed
        or "solution_py" in parsed
        or "unified_diff" in parsed
        or "edits" in parsed
        or "declared_mode" in parsed
    )


def _loads_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        repaired = _repair_triple_quoted_json_strings(text)
        if repaired != text:
            try:
                payload = json.loads(repaired)
            except json.JSONDecodeError:
                raise ModelOutputError(str(exc)) from exc
        else:
            raise ModelOutputError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ModelOutputError("json_payload_not_object")
    return payload


def _repair_triple_quoted_json_strings(text: str) -> str:
    """Convert Python-style triple-quoted string literals into JSON strings.

    Small open-weight models often put multi-line Python function bodies in
    JSON using Python triple-quoted string delimiters. That is not JSON, but
    the intended value is unambiguous when the triple-quoted span is balanced.
    The repaired payload is still passed through normal protocol and source
    validation.
    """

    line_repaired = _repair_line_delimited_triple_quoted_json_strings(text)
    if line_repaired != text:
        return line_repaired

    def replace(match: re.Match[str]) -> str:
        return json.dumps(match.group(1))

    return re.sub(r'"""(.*?)"""', replace, text, flags=re.DOTALL)


def _repair_line_delimited_triple_quoted_json_strings(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    changed = False
    index = 0
    while index < len(lines):
        line = lines[index]
        open_match = re.match(r'^(?P<prefix>.*:\s*)"""(?P<after>.*)$', line, flags=re.DOTALL)
        if open_match is None:
            out.append(line)
            index += 1
            continue

        body_parts = [open_match.group("after")]
        close_index = index + 1
        close_suffix: str | None = None
        while close_index < len(lines):
            candidate = lines[close_index]
            line_no_newline = candidate.rstrip("\n")
            newline = "\n" if candidate.endswith("\n") else ""
            close_match = re.match(r'^\s*"""(?P<suffix>\s*(?:[,}\]].*)?)$', line_no_newline)
            if close_match is not None:
                suffix = close_match.group("suffix")
                if not suffix.strip() and _next_nonempty_line_starts_json_key(lines, close_index + 1):
                    suffix = ","
                close_suffix = suffix + newline
                break
            body_parts.append(candidate)
            close_index += 1

        if close_suffix is None:
            out.append(line)
            index += 1
            continue

        out.append(open_match.group("prefix") + json.dumps("".join(body_parts)) + close_suffix)
        index = close_index + 1
        changed = True
    return "".join(out) if changed else text


def _next_nonempty_line_starts_json_key(lines: list[str], start_index: int) -> bool:
    for line in lines[start_index:]:
        if not line.strip():
            continue
        return re.match(r'^\s*"[^"]+"\s*:', line) is not None
    return False


def _materialize_candidate_source(payload: dict[str, Any], parent_source: str | None) -> str:
    diff_text = payload.get("unified_diff")
    if isinstance(diff_text, str) and diff_text.strip():
        if parent_source is None:
            raise ModelOutputError("parent_source_required_for_unified_diff")
        try:
            return apply_unified_diff(parent_source, diff_text)
        except PatchApplyError as exc:
            raise ModelOutputError(f"unified_diff_apply_failed:{exc}") from exc

    if isinstance(payload.get("solution_py"), str):
        raise ModelOutputError("replacement_file_output_not_allowed")
    raise ModelOutputError("unified_diff_missing_or_empty")
