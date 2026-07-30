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
    ast.Global,
    ast.Import,
    ast.ImportFrom,
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
SPLIT_SEED_OFFSETS = {
    "development": 0,
    "calibration": 1_000_000_007,
    "confirmation": 2_000_000_033,
}


@dataclass(frozen=True)
class PolicyResult:
    ok: bool
    reason: str
    tree: ast.Module | None


def _token(rng: random.Random, length: int = 7) -> str:
    return "".join(rng.choice(string.ascii_lowercase) for _ in range(length))


def _contract(rng: random.Random) -> dict[str, str]:
    error_token = _token(rng, 3)
    return {
        "method": f"invoke_{_token(rng, 3)}",
        "value_keyword": f"item_{_token(rng, 3)}",
        "label_keyword": f"label_{_token(rng, 3)}",
        "weight_keyword": f"weight_{_token(rng, 3)}",
        "scale_keyword": f"scale_{_token(rng, 3)}",
        "value_field": f"result_{_token(rng, 3)}",
        "ticket_field": f"ticket_{_token(rng, 3)}",
        "status_field": f"status_{_token(rng, 3)}",
        "ready_status": f"ready_{_token(rng, 3)}",
        "error": f"Contract{error_token.title()}Error",
    }


def _normalization(
    rng: random.Random, difficulty: str, scalar_kind: str | None = None
) -> dict[str, Any]:
    if difficulty == "scalar":
        kind = scalar_kind or rng.choice(("strip_lower", "strip_upper", "collapse_spaces", "integer_offset"))
        if kind == "strip_lower":
            return {
                "kind": kind,
                "instruction": "convert payload['value'] to str, strip it, then lowercase it and store it as `normalized`",
                "expression": "str(payload['value']).strip().lower()",
                "values": ["  Alpha ", "MiXeD", " two words  "],
            }
        if kind == "strip_upper":
            return {
                "kind": kind,
                "instruction": "convert payload['value'] to str, strip it, then uppercase it and store it as `normalized`",
                "expression": "str(payload['value']).strip().upper()",
                "values": ["  Alpha ", "MiXeD", " two words  "],
            }
        if kind == "collapse_spaces":
            return {
                "kind": kind,
                "instruction": (
                    "convert payload['value'] to str, collapse every whitespace run to one space, and store it as "
                    "`normalized`"
                ),
                "expression": "' '.join(str(payload['value']).split())",
                "values": ["alpha   beta", "  mixed\tspacing ", "one"],
            }
        offset = rng.choice((-3, -1, 2, 4))
        return {
            "kind": kind,
            "instruction": f"convert payload['value'] to int, add {offset}, and store it as `normalized`",
            "expression": f"int(payload['value']) + ({offset})",
            "values": ["4", " -2 ", "13"],
            "offset": offset,
        }
    if difficulty != "list":
        raise ValueError(f"unknown difficulty: {difficulty}")
    kind = rng.choice(("stable_lower", "stable_upper", "stable_spaces", "weighted_integer"))
    if kind in {"stable_lower", "stable_upper", "stable_spaces"}:
        if kind == "stable_lower":
            transform = "str(raw).strip().lower()"
            transform_instruction = "convert it to str, strip it, and lowercase it"
        elif kind == "stable_upper":
            transform = "str(raw).strip().upper()"
            transform_instruction = "convert it to str, strip it, and uppercase it"
        else:
            transform = "' '.join(str(raw).split())"
            transform_instruction = "convert it to str and collapse every whitespace run to one space"
        return {
            "kind": kind,
            "instruction": (
                "iterate over payload['values']; for each item, "
                f"{transform_instruction}; discard empty normalized strings and duplicates while preserving the "
                "first occurrence; join the retained strings with `;` and store that string as `normalized`"
            ),
            "reference_lines": [
                "parts = []",
                "for raw in payload['values']:",
                f"    part = {transform}",
                "    if part and part not in parts:",
                "        parts.append(part)",
                "normalized = ';'.join(parts)",
            ],
            "mutation_target": "if part and part not in parts:",
            "mutation_replacement": "if part:",
            "values": [
                ["  Alpha ", "alpha", "", "Beta"],
                ["MiXeD", " mixed ", "Two Words", "two words"],
                [" one   item ", "one item", "  ", "last"],
            ],
        }
    offset = rng.choice((-3, -1, 2, 4))
    return {
        "kind": kind,
        "instruction": (
            f"convert each item in payload['values'] to int and add {offset}; then store as `normalized` the sum "
            "of each converted number multiplied by its one-based position"
        ),
        "reference_lines": [
            f"numbers = [int(raw) + ({offset}) for raw in payload['values']]",
            "normalized = sum((index + 1) * number for index, number in enumerate(numbers))",
        ],
        "mutation_target": "index + 1",
        "mutation_replacement": "index",
        "values": [["4", "-2", "13"], ["0", "5", "-1", "2"], ["9", "3"]],
        "offset": offset,
    }


def _normalize(spec: dict[str, Any], values: list[Any]) -> Any:
    kind = spec["kind"]
    if kind == "strip_lower":
        return str(values).strip().lower()
    if kind == "strip_upper":
        return str(values).strip().upper()
    if kind == "collapse_spaces":
        return " ".join(str(values).split())
    if kind == "integer_offset":
        return int(values) + int(spec["offset"])
    if kind in {"stable_lower", "stable_upper", "stable_spaces"}:
        parts = []
        for raw in values:
            if kind == "stable_lower":
                part = str(raw).strip().lower()
            elif kind == "stable_upper":
                part = str(raw).strip().upper()
            else:
                part = " ".join(str(raw).split())
            if part and part not in parts:
                parts.append(part)
        return ";".join(parts)
    if kind == "weighted_integer":
        numbers = [int(raw) + int(spec["offset"]) for raw in values]
        return sum((index + 1) * number for index, number in enumerate(numbers))
    raise ValueError(f"unknown normalization: {kind}")


def _context(rng: random.Random) -> dict[str, Any]:
    casing = rng.choice(("lower", "upper"))
    offset = rng.choice((-2, 1, 3, 5))
    return {
        "instruction": f"convert payload['label'] to str, strip it, then {casing}case it",
        "expression": f"str(payload['label']).strip().{casing}()",
        "scale_instruction": "convert payload['scale'] to int and clamp it to the inclusive range 1 through 4",
        "scale_expression": "max(1, min(4, int(payload['scale'])))",
        "weight_instruction": f"set `weight` to (len(label) plus {offset}) multiplied by `scale`",
        "weight_expression": f"(len(label) + ({offset})) * scale",
        "weight_offset": offset,
        "labels": ["  North Star ", "Beta-2", " mixed Label  "],
        "scales": ["0", "2", "7"],
    }


def _context_values(spec: dict[str, Any], value: Any, raw_scale: Any) -> tuple[str, int, int]:
    label = str(value).strip()
    if ".lower()" in spec["expression"]:
        label = label.lower()
    else:
        label = label.upper()
    scale = max(1, min(4, int(raw_scale)))
    weight = (len(label) + int(spec["weight_offset"])) * scale
    return label, scale, weight


def _server_value(task: dict[str, Any], normalized: Any) -> Any:
    if task["normalization"]["kind"] in {"integer_offset", "weighted_integer"}:
        return normalized * int(task["server_multiplier"])
    return f"{normalized}|{task['server_suffix']}"


def _postprocess_value(task: dict[str, Any], server_value: Any, label: str, scale: int, weight: int) -> Any:
    if task["normalization"]["kind"] in {"integer_offset", "weighted_integer"}:
        return (int(server_value) + weight) * int(task["post_multiplier"]) - scale
    base = str(server_value).split("|", 1)[0]
    return f"{base[::-1]}:{label}:{weight - scale}"


def _postprocess(task: dict[str, Any], contract: dict[str, str], response_name: str = "response") -> tuple[str, str]:
    value = f"{response_name}.{contract['value_field']}"
    if task["normalization"]["kind"] in {"integer_offset", "weighted_integer"}:
        expression = f"(int({value}) + weight) * {task['post_multiplier']} - scale"
        instruction = (
            "set `base` to the documented value attribute converted to int plus `weight`; then set `value` to "
            f"(`base` multiplied by {task['post_multiplier']}) minus `scale`"
        )
    else:
        expression = f"str({value}).split('|', 1)[0][::-1] + ':' + label + ':' + str(weight - scale)"
        instruction = (
            "convert the documented value attribute to str, take the part before the first `|`, reverse that part, "
            "then append `:`, `label`, another `:`, and `weight - scale` converted to str"
        )
    return expression, instruction


def reference_code(task: dict[str, Any], shard: int) -> str:
    contract = task["contracts"][shard]
    postprocess_expression, _ = _postprocess(task, contract, "r")
    fallback = repr(task["fallback"])
    if "reference_lines" in task["normalization"]:
        normalization_code = "".join(f"    {line}\n" for line in task["normalization"]["reference_lines"])
    else:
        normalization_code = f"    normalized = {task['normalization']['expression']}\n"
    return (
        "def adapt(client, payload):\n"
        f"{normalization_code}"
        f"    label = {task['context']['expression']}\n"
        f"    scale = {task['context']['scale_expression']}\n"
        f"    weight = {task['context']['weight_expression']}\n"
        "    try:\n"
        f"        r = client.{contract['method']}({contract['value_keyword']}=normalized, "
        f"{contract['label_keyword']}=label, {contract['scale_keyword']}=scale, "
        f"{contract['weight_keyword']}=weight)\n"
        f"    except {contract['error']}:\n"
        f"        return {{'ok': False, 'value': {fallback}, 'ticket': None}}\n"
        f"    ticket = r.{contract['ticket_field']}\n"
        f"    if r.{contract['status_field']} != {contract['ready_status']!r}:\n"
        f"        return {{'ok': False, 'value': {fallback}, 'ticket': ticket}}\n"
        f"    return {{'ok': True, 'value': {postprocess_expression}, 'ticket': ticket}}\n"
    )


def task_prompt(task: dict[str, Any], shard: int) -> str:
    contract = task["contracts"][shard]
    _, postprocess_instruction = _postprocess(task, contract)
    return f"""Implement target.py.

The file must define exactly this function:

    def adapt(client, payload):

Required behavior:
1. {task['normalization']['instruction']}.
2. {task['context']['instruction']} and store the result as `label`; then
   {task['context']['scale_instruction']} and store the result as `scale`;
   finally, {task['context']['weight_instruction']}.
3. Call the client API described by the evidence shard, passing all four
   documented keyword arguments.
4. The response is an object, not a mapping: access all documented fields with
   dot notation. Read `ticket` from its ticket attribute. If its status
   attribute is not exactly {contract['ready_status']!r}, return
   {{"ok": False, "value": {task['fallback']!r}, "ticket": ticket}}.
5. For a ready response, {postprocess_instruction}. Return that result as
   {{"ok": True, "value": value, "ticket": ticket}}.
6. If the documented contract exception is raised, return
   {{"ok": False, "value": {task['fallback']!r}, "ticket": None}}.

Evidence shard {shard}:
- method: client.{contract['method']}
- normalized-value keyword: {contract['value_keyword']}
- label keyword: {contract['label_keyword']}
- scale keyword: {contract['scale_keyword']}
- weight keyword: {contract['weight_keyword']}
- value attribute: response.{contract['value_field']}
- ticket attribute: response.{contract['ticket_field']}
- status attribute: response.{contract['status_field']}
- ready status: {contract['ready_status']!r}
- contract exception: {contract['error']}

Constraints:
- Do not import anything.
- Do not inspect the client dynamically.
- Do not support multiple contracts or alternate method names.
- Use direct payload indexing; do not add defaults for missing inputs.
- Use no comments, docstrings, helper functions, or explanatory text.
- Keep the function at most 24 nonblank lines.
- Return only one Python code block containing the complete function.
"""


def generate_task(seed: int, split: str, mode: int, index: int, difficulty: str = "scalar") -> dict[str, Any]:
    if mode not in (0, 1, 2):
        raise ValueError("mode must be 0, 1, or 2")
    if split not in SPLIT_SEED_OFFSETS:
        raise ValueError(f"unknown split: {split}")
    task_seed = (seed + 1) * 1_000_003 + mode * 10_007 + index + SPLIT_SEED_OFFSETS[split]
    rng = random.Random(task_seed)
    contracts = [_contract(rng) for _ in range(3)]
    scalar_kinds = ("strip_lower", "strip_upper", "collapse_spaces", "integer_offset")
    normalization = _normalization(
        rng,
        difficulty,
        scalar_kind=scalar_kinds[index % len(scalar_kinds)] if difficulty == "scalar" else None,
    )
    task = {
        "schema_version": 5 if difficulty == "scalar" else 6,
        "task_id": f"sai3-{split}-m{mode}-{index:04d}",
        "split": split,
        "task_seed": task_seed,
        "mode": mode,
        "difficulty": difficulty,
        "contracts": contracts,
        "normalization": normalization,
        "task_stratum": normalization["kind"],
        "context": _context(rng),
        "fallback": f"unavailable_{_token(rng, 5)}",
        "server_suffix": _token(rng, 5),
        "server_multiplier": rng.choice((2, 3, 5)),
        "post_multiplier": rng.choice((2, 3, 4)),
        "ticket_prefix": _token(rng, 4),
        "not_ready_status": f"pending_{_token(rng, 5)}",
    }
    task["prompts"] = [task_prompt(task, shard) for shard in range(3)]
    task["references"] = [reference_code(task, shard) for shard in range(3)]
    return task


def generate_tasks(seed: int, split: str, tasks_per_mode: int, difficulty: str = "scalar") -> list[dict[str, Any]]:
    return [
        generate_task(seed=seed, split=split, mode=mode, index=index, difficulty=difficulty)
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
    if len(list(ast.walk(tree))) > 350:
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
        expected_keywords = {
            contract["value_keyword"],
            contract["label_keyword"],
            contract["scale_keyword"],
            contract["weight_keyword"],
        }
        if set(kwargs) != expected_keywords:
            raise TypeError("wrong keyword")
        normalized = kwargs[contract["value_keyword"]]
        label = kwargs[contract["label_keyword"]]
        scale = kwargs[contract["scale_keyword"]]
        weight = kwargs[contract["weight_keyword"]]
        expected_weight = (len(label) + int(task["context"]["weight_offset"])) * scale
        if not 1 <= scale <= 4 or weight != expected_weight:
            raise ValueError("wrong derived weight")
        response = response_type()
        setattr(response, contract["value_field"], _server_value(task, normalized))
        setattr(response, contract["ticket_field"], f"{task['ticket_prefix']}:{label}:{scale}:{weight}")
        status = task["not_ready_status"] if self.force_not_ready else contract["ready_status"]
        setattr(response, contract["status_field"], status)
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

    tests: list[tuple[dict[str, Any], bool, bool, dict[str, Any]]] = []
    value_key = "values" if task["normalization"]["kind"].startswith(("stable_", "weighted_")) else "value"
    cases = zip(task["normalization"]["values"], task["context"]["labels"], task["context"]["scales"])
    for values, raw_label, raw_scale in cases:
        normalized = _normalize(task["normalization"], values)
        label, scale, weight = _context_values(task["context"], raw_label, raw_scale)
        ticket = f"{task['ticket_prefix']}:{label}:{scale}:{weight}"
        tests.append(
            (
                {value_key: values, "label": raw_label, "scale": raw_scale},
                False,
                False,
                {
                    "ok": True,
                    "value": _postprocess_value(task, _server_value(task, normalized), label, scale, weight),
                    "ticket": ticket,
                },
            )
        )
    first_values = task["normalization"]["values"][0]
    first_raw_label = task["context"]["labels"][0]
    first_raw_scale = task["context"]["scales"][0]
    first_label, first_scale, first_weight = _context_values(task["context"], first_raw_label, first_raw_scale)
    first_ticket = f"{task['ticket_prefix']}:{first_label}:{first_scale}:{first_weight}"
    tests.append(
        (
            {value_key: first_values, "label": first_raw_label, "scale": first_raw_scale},
            False,
            True,
            {"ok": False, "value": task["fallback"], "ticket": first_ticket},
        )
    )
    tests.append(
        (
            {value_key: first_values, "label": first_raw_label, "scale": first_raw_scale},
            True,
            False,
            {"ok": False, "value": task["fallback"], "ticket": None},
        )
    )

    for test_index, (payload, force_error, force_not_ready, expected) in enumerate(tests):
        client = client_type()
        client.force_error = force_error
        client.force_not_ready = force_not_ready
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
    if "mutation_target" in task["normalization"]:
        normalization_mutant = correct.replace(
            task["normalization"]["mutation_target"],
            task["normalization"]["mutation_replacement"],
        )
    else:
        normalization_mutant = correct.replace(task["normalization"]["expression"], "payload['value']")
    mutants = [
        reference_code(task, (mode + 1) % 3),
        reference_code(task, (mode + 2) % 3),
        correct.replace(contract["value_field"], other["value_field"]),
        normalization_mutant,
        correct.replace(task["context"]["expression"], "str(payload['label'])"),
        correct.replace(task["context"]["scale_expression"], "int(payload['scale'])"),
        correct.replace(task["context"]["weight_expression"], "len(label)"),
        correct.replace(contract["ticket_field"], other["ticket_field"]),
        correct.replace(contract["status_field"], other["status_field"]),
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
