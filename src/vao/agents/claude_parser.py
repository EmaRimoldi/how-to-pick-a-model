"""Parsing and validation helpers for Claude/Anthropic backend outputs."""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from pydantic import ValidationError

from vao.schemas import ModeDistribution
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


def parse_edit_payload(raw_text: str, expected_mode: str) -> dict[str, Any]:
    validate_mode(expected_mode)
    payload = parse_json_object(raw_text)
    declared = payload.get("declared_mode")
    if declared != expected_mode:
        raise ModelOutputError(f"declared_mode_mismatch:{declared!r}!={expected_mode!r}")
    source = payload.get("solution_py")
    if not isinstance(source, str) or not source.strip():
        raise ModelOutputError("solution_py_missing_or_empty")
    validation = validate_candidate_source(source)
    if not validation["passed"]:
        raise ModelOutputError("candidate_source_invalid:" + ";".join(validation["errors"]))
    return {**payload, "source_validation": validation}


def validate_candidate_source(source: str) -> dict[str, Any]:
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


def _looks_like_protocol_object(parsed: dict[str, Any]) -> bool:
    return "mode_probs" in parsed or "solution_py" in parsed or "declared_mode" in parsed


def _loads_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelOutputError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise ModelOutputError("json_payload_not_object")
    return payload
