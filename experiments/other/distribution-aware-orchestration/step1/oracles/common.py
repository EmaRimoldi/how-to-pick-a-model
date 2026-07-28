"""Shared inference-time oracle helpers."""

from __future__ import annotations

import ast
import doctest
from typing import Any


def function_signature(prompt: str) -> dict[str, Any]:
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return {"name": None, "args": []}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return {"name": node.name, "args": [arg.arg for arg in node.args.args]}
    return {"name": None, "args": []}


def public_examples(prompt: str, entry_point: str) -> list[str]:
    namespace: dict[str, Any] = {}
    try:
        tree = ast.parse(prompt)
    except SyntaxError:
        return []
    examples: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == entry_point:
            doc = ast.get_docstring(node) or ""
            parsed = doctest.DocTestParser().get_doctest(doc, namespace, entry_point, None, 0)
            examples.extend(example.source.strip() for example in parsed.examples)
    return examples


def ok(**extra: Any) -> dict[str, Any]:
    return {"passed": True, **extra}


def fail(reason: str, **extra: Any) -> dict[str, Any]:
    return {"passed": False, "reason": reason, **extra}
