"""Inference oracle for the understand_spec node."""

from __future__ import annotations

from typing import Any

from oracles.common import fail, function_signature, ok, public_examples


def check(instance: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    signature = function_signature(instance["prompt"])
    if signature["name"] != instance["entry_point"]:
        return fail("prompt_signature_does_not_match_entry_point", expected=instance["entry_point"], got=signature["name"])
    spec = state.get("spec_struct", state)
    if spec.get("signature", {}).get("name") not in {signature["name"], None}:
        return fail("spec_signature_name_mismatch")
    prompt_examples = public_examples(instance["prompt"], instance["entry_point"])
    spec_examples = spec.get("examples") or []
    if prompt_examples and len(spec_examples) < len(prompt_examples):
        return fail("missing_public_examples", expected=len(prompt_examples), got=len(spec_examples))
    if "edge_cases" not in spec or "invariants" not in spec:
        return fail("missing_spec_fields")
    return ok(public_examples=len(prompt_examples), spec_examples=len(spec_examples))

