"""Shared inference-time oracle helpers."""

from __future__ import annotations

import ast
import doctest
import re
from typing import Any


DEF_RE = re.compile(r"def\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^)]*)\)\s*:")


def function_signature(prompt: str) -> dict[str, Any]:
    match = DEF_RE.search(prompt)
    if not match:
        return {"name": None, "args": []}
    args = []
    for raw in match.group("args").split(","):
        value = raw.strip()
        if not value:
            continue
        args.append(value.split(":", 1)[0].split("=", 1)[0].strip())
    return {"name": match.group("name"), "args": args}


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

