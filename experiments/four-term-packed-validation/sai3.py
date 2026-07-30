#!/usr/bin/env python3
"""Procedural SAI-3 tasks and deterministic verifier.

The benchmark hides one of three incompatible API contracts. A solver sees the
common task and one evidence shard. Only the true shard contains identifiers
that exist in the verifier runtime.
"""

from __future__ import annotations

import ast
import copy
import json
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "hasattr",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
FORBIDDEN_NODES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.For,
    ast.GeneratorExp,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.ListComp,
    ast.Lambda,
    ast.Nonlocal,
    ast.SetComp,
    ast.DictComp,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
SAFE_BUILTINS = {
    "abs": abs,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


@dataclass(frozen=True)
class PolicyResult:
    ok: bool
    reason: str
    tree: ast.Module | None


def _token(rng: random.Random, length: int = 7) -> str:
    return "".join(rng.choice(string.ascii_lowercase) for _ in range(length))


def _contract(rng: random.Random) -> dict[str, str]:
    error_token = _token(rng, 6)
    return {
        "method": f"invoke_{_token(rng)}",
        "keyword": f"item_{_token(rng)}",
        "field": f"result_{_token(rng)}",
        "error": f"Contract{error_token.title()}Error",
    }


def _normalization(rng: random.Random) -> dict[str, Any]:
    kind = rng.choice(("strip_lower", "strip_upper", "collapse_spaces", "integer_offset"))
    if kind == "strip_lower":
        return {
            "kind": kind,
            "instruction": "convert payload['value'] to str, strip it, then lowercase it",
            "expression": "str(payload['value']).strip().lower()",
            "values": ["  Alpha ", "MiXeD", " two words  "],
        }
    if kind == "strip_upper":
        return {
            "kind": kind,
            "instruction": "convert payload['value'] to str, strip it, then uppercase it",
            "expression": "str(payload['value']).strip().upper()",
            "values": ["  Alpha ", "MiXeD", " two words  "],
        }
    if kind == "collapse_spaces":
        return {
            "kind": kind,
            "instruction": "convert payload['value'] to str and collapse all whitespace runs to one space",
            "expression": "' '.join(str(payload['value']).split())",
            "values": ["alpha   beta", "  mixed\tspacing ", "one"],
        }
    offset = rng.choice((-3, -1, 2, 4))
    return {
        "kind": kind,
        "instruction": f"convert payload['value'] to int and add {offset}",
        "expression": f"int(payload['value']) + ({offset})",
        "values": ["4", " -2 ", "13"],
        "offset": offset,
    }


def _normalize(spec: dict[str, Any], value: Any) -> Any:
    kind = spec["kind"]
    if kind == "strip_lower":
        return str(value).strip().lower()
    if kind == "strip_upper":
        return str(value).strip().upper()
    if kind == "collapse_spaces":
        return " ".join(str(value).split())
    if kind == "integer_offset":
        return int(value) + int(spec["offset"])
    raise ValueError(f"unknown normalization: {kind}")


def _server_value(task: dict[str, Any], normalized: Any) -> Any:
    if task["normalization"]["kind"] == "integer_offset":
        return normalized * int(task["server_multiplier"])
    return f"{normalized}|{task['server_suffix']}"


def reference_code(task: dict[str, Any], shard: int) -> str:
    contract = task["contracts"][shard]
    expression = task["normalization"]["expression"]
    fallback = repr(task["fallback"])
    return (
        "def adapt(client, payload):\n"
        f"    normalized = {expression}\n"
        "    try:\n"
        f"        response = client.{contract['method']}({contract['keyword']}=normalized)\n"
        f"    except {contract['error']}:\n"
        f"        return {{'ok': False, 'value': {fallback}}}\n"
        f"    return {{'ok': True, 'value': response.{contract['field']}}}\n"
    )


def task_prompt(task: dict[str, Any], shard: int) -> str:
    contract = task["contracts"][shard]
    return f"""Implement target.py.

The file must define exactly this function:

    def adapt(client, payload):

Required behavior:
1. {task['normalization']['instruction']} and store the result as `normalized`.
2. Call the client API described by the evidence shard below, passing `normalized`.
3. On success return {{"ok": True, "value": <the documented response field>}}.
4. If the documented contract exception is raised, return
   {{"ok": False, "value": {task['fallback']!r}}}.

Evidence shard {shard}:
- method: client.{contract['method']}
- required keyword argument: {contract['keyword']}
- response field: {contract['field']}
- contract exception: {contract['error']}

Constraints:
- Do not import anything.
- Do not inspect the client dynamically.
- Do not support multiple contracts or alternate method names.
- Return only one Python code block containing the complete function.
"""


def generate_task(seed: int, split: str, mode: int, index: int) -> dict[str, Any]:
    if mode not in (0, 1, 2):
        raise ValueError("mode must be 0, 1, or 2")
    rng = random.Random((seed + 1) * 1_000_003 + mode * 10_007 + index)
    contracts = [_contract(rng) for _ in range(3)]
    normalization = _normalization(rng)
    task = {
        "schema_version": 1,
        "task_id": f"sai3-{split}-m{mode}-{index:04d}",
        "split": split,
        "mode": mode,
        "contracts": contracts,
        "normalization": normalization,
        "fallback": f"unavailable_{_token(rng, 5)}",
        "server_suffix": _token(rng, 5),
        "server_multiplier": rng.choice((2, 3, 5)),
    }
    task["prompts"] = [task_prompt(task, shard) for shard in range(3)]
    task["references"] = [reference_code(task, shard) for shard in range(3)]
    return task


def generate_tasks(seed: int, split: str, tasks_per_mode: int) -> list[dict[str, Any]]:
    return [
        generate_task(seed=seed, split=split, mode=mode, index=index)
        for mode in range(3)
        for index in range(tasks_per_mode)
    ]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    start = text.find("def adapt")
    return text[start:].strip() if start >= 0 else text.strip()


def check_policy(code: str) -> PolicyResult:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return PolicyResult(False, f"syntax:{exc.msg}", None)

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return PolicyResult(False, "one_top_level_function_required", tree)
    function = tree.body[0]
    if function.name != "adapt":
        return PolicyResult(False, "function_must_be_adapt", tree)
    arg_names = [arg.arg for arg in function.args.args]
    if arg_names != ["client", "payload"]:
        return PolicyResult(False, "signature_must_be_client_payload", tree)
    if len(list(ast.walk(tree))) > 120:
        return PolicyResult(False, "program_too_large", tree)

    client_methods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            return PolicyResult(False, f"forbidden_node:{type(node).__name__}", tree)
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return PolicyResult(False, "dunder_attribute", tree)
            if isinstance(node.value, ast.Name) and node.value.id == "client":
                client_methods.add(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                return PolicyResult(False, f"forbidden_call:{node.func.id}", tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            return PolicyResult(False, "power_operator", tree)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and abs(node.value) > 1_000_000:
                return PolicyResult(False, "numeric_literal_too_large", tree)
            if isinstance(node.value, (str, bytes)) and len(node.value) > 10_000:
                return PolicyResult(False, "literal_too_large", tree)

    if len(client_methods) != 1:
        return PolicyResult(False, "exactly_one_client_method_required", tree)
    return PolicyResult(True, "ok", tree)


def _runtime(task: dict[str, Any]) -> tuple[type, type, type]:
    contract = task["contracts"][task["mode"]]
    error_type = type(contract["error"], (Exception,), {})
    response_type = type("ContractResponse", (), {})

    def invoke(self: Any, **kwargs: Any) -> Any:
        if self.force_error:
            raise error_type("forced verifier path")
        if set(kwargs) != {contract["keyword"]}:
            raise TypeError("wrong keyword")
        response = response_type()
        setattr(
            response,
            contract["field"],
            _server_value(task, kwargs[contract["keyword"]]),
        )
        return response

    client_type = type("HiddenClient", (), {contract["method"]: invoke})
    return client_type, response_type, error_type


def verify_code(task: dict[str, Any], code: str) -> dict[str, Any]:
    policy = check_policy(code)
    if not policy.ok or policy.tree is None:
        return {"passed": False, "parsed": policy.tree is not None, "policy_ok": False, "reason": policy.reason}

    client_type, _, error_type = _runtime(task)
    contract = task["contracts"][task["mode"]]
    namespace: dict[str, Any] = {}
    globals_dict = {"__builtins__": SAFE_BUILTINS, contract["error"]: error_type}
    try:
        exec(compile(policy.tree, "<candidate>", "exec"), globals_dict, namespace)
        function = namespace["adapt"]
    except Exception as exc:  # noqa: BLE001 - verifier reports model failures.
        return {"passed": False, "parsed": True, "policy_ok": True, "reason": f"load:{type(exc).__name__}"}

    tests: list[tuple[dict[str, Any], bool, dict[str, Any]]] = []
    for value in task["normalization"]["values"]:
        normalized = _normalize(task["normalization"], value)
        tests.append(
            (
                {"value": value},
                False,
                {"ok": True, "value": _server_value(task, normalized)},
            )
        )
    tests.append(({"value": task["normalization"]["values"][0]}, True, {"ok": False, "value": task["fallback"]}))

    for test_index, (payload, force_error, expected) in enumerate(tests):
        client = client_type()
        client.force_error = force_error
        try:
            observed = function(client, copy.deepcopy(payload))
        except Exception as exc:  # noqa: BLE001 - verifier reports model failures.
            return {
                "passed": False,
                "parsed": True,
                "policy_ok": True,
                "reason": f"test_{test_index}:{type(exc).__name__}",
            }
        if observed != expected:
            return {
                "passed": False,
                "parsed": True,
                "policy_ok": True,
                "reason": f"test_{test_index}:wrong_output",
            }
    return {"passed": True, "parsed": True, "policy_ok": True, "reason": "ok"}


def verify_completion(task: dict[str, Any], text: str) -> dict[str, Any]:
    code = extract_code(text)
    result = verify_code(task, code)
    result["code"] = code
    return result


def reference_mutants(task: dict[str, Any]) -> list[str]:
    mode = task["mode"]
    contract = task["contracts"][mode]
    other = task["contracts"][(mode + 1) % 3]
    correct = reference_code(task, mode)
    mutants = [
        reference_code(task, (mode + 1) % 3),
        reference_code(task, (mode + 2) % 3),
        correct.replace(contract["field"], other["field"]),
        correct.replace(task["normalization"]["expression"], "payload['value']"),
        correct.replace(repr(task["fallback"]), repr(task["fallback"] + "_wrong")),
    ]
    return mutants


def audit_task(task: dict[str, Any], deterministic_reruns: int = 20) -> dict[str, Any]:
    correct = reference_code(task, task["mode"])
    correct_results = [verify_code(task, correct)["passed"] for _ in range(deterministic_reruns)]
    wrong_results = [
        verify_code(task, reference_code(task, shard))["passed"]
        for shard in range(3)
        if shard != task["mode"]
    ]
    mutant_results = [verify_code(task, mutant)["passed"] for mutant in reference_mutants(task)]
    mutation_score = 1.0 - sum(mutant_results) / len(mutant_results)
    return {
        "task_id": task["task_id"],
        "correct_reference_passes": all(correct_results),
        "deterministic": len(set(correct_results)) == 1,
        "wrong_reference_acceptances": sum(wrong_results),
        "mutation_score": mutation_score,
        "gate_passed": (
            all(correct_results)
            and len(set(correct_results)) == 1
            and not any(wrong_results)
            and mutation_score >= 0.95
        ),
    }
