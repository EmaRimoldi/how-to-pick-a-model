"""Generate per-node HumanEval records with the local Codex CLI suite.

All model access for Step 1 lives in this file. Runners consume the resulting
JSONL deterministically and never call models.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from tqdm import tqdm

from runners.common import DATA_DIR, LOGS_DIR, REPO_ROOT, ensure_step1_dirs, read_jsonl, write_jsonl
from runners.sandbox import run_generated_tests, run_public_examples
from runners.workflow import (
    MODEL_NODE_IDS,
    assert_public_solving_instance,
    load_node_record_map,
    validate_node_record_coverage,
)

SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from vao.agents.codex_cli_adapter import CodexCliAdapter  # noqa: E402


Role = Literal["seed", "cheap"]
DEFAULT_OUTPUTS = {
    "seed": LOGS_DIR / "seed_solver_completions.jsonl",
    "cheap": LOGS_DIR / "cheap_node_completions.jsonl",
}


@dataclass(frozen=True)
class BackendConfig:
    model: str
    reasoning_effort: str
    timeout_seconds: int
    sandbox: str
    use_output_schema: bool


def _load_config(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    config_path = Path(path)
    payload = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(payload) or {}
    return json.loads(payload)


def _config_value(config: dict[str, Any], *keys: str) -> Any:
    current: Any = config
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _resolve_backend(role: Role, config_path: str | None) -> BackendConfig:
    config = _load_config(config_path)
    role_key = "seed_model" if role == "seed" else "node_model"
    model_env = "SEED_MODEL" if role == "seed" else "NODE_MODEL"
    model = os.environ.get(model_env) or _config_value(config, role_key) or _config_value(config, "models", role)
    if not model:
        raise SystemExit(f"Missing model configuration: set {model_env} or pass --config with {role_key}.")

    reasoning_env = "SEED_REASONING_EFFORT" if role == "seed" else "NODE_REASONING_EFFORT"
    default_reasoning = "xhigh" if role == "seed" else "low"
    reasoning_effort = (
        os.environ.get(reasoning_env)
        or _config_value(config, f"{role}_reasoning_effort")
        or _config_value(config, "reasoning_effort", role)
        or default_reasoning
    )
    timeout_seconds = int(
        os.environ.get("CODEX_TIMEOUT_SECONDS")
        or _config_value(config, "timeout_seconds")
        or _config_value(config, "codex", "timeout_seconds")
        or 900
    )
    sandbox = str(
        os.environ.get("CODEX_SANDBOX")
        or _config_value(config, "sandbox")
        or _config_value(config, "codex", "sandbox")
        or "read-only"
    )
    return BackendConfig(
        model=str(model),
        reasoning_effort=str(reasoning_effort),
        timeout_seconds=timeout_seconds,
        sandbox=sandbox,
        use_output_schema=bool(_config_value(config, "use_output_schema") if "use_output_schema" in config else True),
    )


def _adapter(backend: BackendConfig) -> CodexCliAdapter:
    return CodexCliAdapter(
        model_id=backend.model,
        reasoning_effort=backend.reasoning_effort,
        timeout_seconds=backend.timeout_seconds,
        sandbox=backend.sandbox,
        use_output_schema=backend.use_output_schema,
        working_dir=REPO_ROOT,
        retries=0,
    )


def _json_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


SPEC_SCHEMA = _json_schema(
    {
        "signature": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "args"],
            "additionalProperties": False,
        },
        "docstring_summary": {"type": "string"},
        "input_types": {"type": "array", "items": {"type": "string"}},
        "output_type": {"type": "string"},
        "examples": {"type": "array", "items": {"type": "string"}},
        "edge_cases": {"type": "array", "items": {"type": "string"}},
        "invariants": {"type": "array", "items": {"type": "string"}},
    },
    ["signature", "docstring_summary", "input_types", "output_type", "examples", "edge_cases", "invariants"],
)
PLAN_SCHEMA = _json_schema(
    {
        "algorithm": {"type": "string"},
        "cases": {"type": "array", "items": {"type": "string"}},
        "complexity": {"type": "string"},
        "implementation_notes": {"type": "array", "items": {"type": "string"}},
    },
    ["algorithm", "cases", "complexity", "implementation_notes"],
)
TEST_SCHEMA = _json_schema(
    {
        "tests": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    ["tests", "rationale"],
)
IMPLEMENT_SCHEMA = _json_schema(
    {
        "completion": {"type": "string"},
        "notes": {"type": "string"},
    },
    ["completion", "notes"],
)
REPAIR_SCHEMA = _json_schema(
    {
        "completion": {"type": "string"},
        "repair_summary": {"type": "string"},
    },
    ["completion", "repair_summary"],
)


def _base_context(instance: dict[str, Any]) -> str:
    return (
        f"task_id: {instance['task_id']}\n"
        f"entry_point: {instance['entry_point']}\n\n"
        "HumanEval prompt, including signature and public docstring examples:\n"
        f"{instance['prompt']}\n\n"
        "Hard rule: use only this prompt and public examples. Do not use hidden tests, verifier code, "
        "reference solutions, or ground-truth answers."
    )


def _node_prompt(node_id: str, instance: dict[str, Any], state: dict[str, Any]) -> str:
    context = _base_context(instance)
    if node_id == "understand_spec":
        return (
            "Node: understand_spec.\n"
            "Extract the function signature, public examples, edge cases, and invariants. "
            "Do not solve the task.\n\n"
            f"{context}"
        )
    if node_id == "plan":
        return (
            "Node: plan.\n"
            "Given the prompt-derived spec, write a concise implementation plan without code.\n\n"
            f"{context}\n\nspec_struct:\n{json.dumps(state['understand_spec'], indent=2, sort_keys=True)}"
        )
    if node_id == "generate_tests":
        return (
            "Node: generate_tests.\n"
            "Write Python assertion statements that call the entry point. Include public examples and a few "
            "prompt-derived edge cases. These tests will run only on the candidate, never on gold during solving.\n\n"
            f"{context}\n\nspec_struct:\n{json.dumps(state['understand_spec'], indent=2, sort_keys=True)}\n\n"
            f"plan_struct:\n{json.dumps(state['plan'], indent=2, sort_keys=True)}"
        )
    if node_id == "implement":
        return (
            "Node: implement.\n"
            "Return only the function body completion to append after the prompt. Do not include imports, "
            "the function signature, markdown, explanations, or tests.\n\n"
            f"{context}\n\nspec_struct:\n{json.dumps(state['understand_spec'], indent=2, sort_keys=True)}\n\n"
            f"plan_struct:\n{json.dumps(state['plan'], indent=2, sort_keys=True)}\n\n"
            f"test_suite:\n{json.dumps(state['generate_tests'], indent=2, sort_keys=True)}"
        )
    if node_id == "repair":
        retry_feedback = ""
        if state.get("repair_retry_feedback"):
            retry_feedback = (
                "\n\nprevious_repair_feedback:\n"
                f"{json.dumps(state['repair_retry_feedback'], indent=2, sort_keys=True)}"
            )
        return (
            "Node: repair.\n"
            "Revise the candidate completion using only the prompt, public/generated test feedback, and previous "
            "node outputs. Return a replacement function body completion. If any provided feedback failed, the "
            "replacement must differ from the candidate; return the same body only when the candidate already "
            "passes all provided feedback.\n\n"
            f"{context}\n\nspec_struct:\n{json.dumps(state['understand_spec'], indent=2, sort_keys=True)}\n\n"
            f"plan_struct:\n{json.dumps(state['plan'], indent=2, sort_keys=True)}\n\n"
            f"test_suite:\n{json.dumps(state['generate_tests'], indent=2, sort_keys=True)}\n\n"
            f"candidate_completion:\n{state['implement']['completion']}\n\n"
            f"candidate_public_feedback:\n{json.dumps(state.get('candidate_public_feedback', {}), indent=2, sort_keys=True)}\n\n"
            f"candidate_generated_feedback:\n{json.dumps(state.get('candidate_generated_feedback', {}), indent=2, sort_keys=True)}"
            f"{retry_feedback}"
        )
    raise KeyError(node_id)


def _schema_for(node_id: str) -> dict[str, Any]:
    return {
        "understand_spec": SPEC_SCHEMA,
        "plan": PLAN_SCHEMA,
        "generate_tests": TEST_SCHEMA,
        "implement": IMPLEMENT_SCHEMA,
        "repair": REPAIR_SCHEMA,
    }[node_id]


def _strip_code_fence(text: str) -> str:
    without_outer_newlines = text.strip("\n")
    stripped_for_fence = without_outer_newlines.strip()
    if stripped_for_fence.startswith("```"):
        stripped_for_fence = re.sub(r"^```[A-Za-z0-9_-]*[ \t]*(?:\r?\n)?", "", stripped_for_fence)
        stripped_for_fence = re.sub(r"\s*```$", "", stripped_for_fence)
        return stripped_for_fence.strip("\n")
    return without_outer_newlines


def _extract_full_function_body(text: str, entry_point: str) -> str | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == entry_point and node.body:
            start = min(child.lineno for child in node.body) - 1
            end = max(getattr(child, "end_lineno", child.lineno) for child in node.body)
            return "\n".join(lines[start:end])
    return None


def normalize_completion(raw: str, *, prompt: str, entry_point: str) -> str:
    text = _strip_code_fence(raw)
    if prompt and text.startswith(prompt.strip()):
        text = text[len(prompt.strip()) :].lstrip("\n")
    body = _extract_full_function_body(text, entry_point)
    if body is not None:
        text = body
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return "    pass\n"
    if all((not line.strip()) or line.startswith((" ", "\t")) for line in lines):
        normalized = "\n".join(lines)
    else:
        normalized = textwrap.indent("\n".join(lines), "    ")
    return normalized.rstrip() + "\n"


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = _strip_code_fence(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("model output is not a JSON object")
    return payload


def _token_usage(usage: dict[str, Any], *, wall_ms: int, model: str, reasoning_effort: str) -> dict[str, Any]:
    nested = usage.get("usage") if isinstance(usage.get("usage"), dict) else usage
    total = int(nested.get("total_tokens") or nested.get("tokens_used") or 0)
    prompt_tokens = int(nested.get("prompt_tokens") or nested.get("input_tokens") or 0)
    completion_tokens = int(nested.get("completion_tokens") or nested.get("output_tokens") or 0)
    if total and not (prompt_tokens or completion_tokens):
        # Codex CLI may expose only total tokens. Keep the real total and mark
        # the split source; T_k still uses the actual total token count.
        prompt_tokens = total
    return {
        "calls": 1,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total or prompt_tokens + completion_tokens,
        "wall_ms": wall_ms,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "transport": usage.get("transport", "codex_cli"),
        "token_split_source": "codex_usage" if completion_tokens else "codex_total_only",
    }


def _merge_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in ("calls", "prompt_tokens", "completion_tokens", "total_tokens", "wall_ms"):
        merged[key] = int(left.get(key) or 0) + int(right.get(key) or 0)
    return merged


def _call_node(
    *,
    adapter: CodexCliAdapter,
    backend: BackendConfig,
    node_id: str,
    instance: dict[str, Any],
    state: dict[str, Any],
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    prompt = _node_prompt(node_id, instance, state)
    started = time.perf_counter()
    raw, usage = adapter._complete(prompt, _schema_for(node_id), max_tokens=max_tokens)
    wall_ms = int((time.perf_counter() - started) * 1000)
    payload = _parse_json_object(raw)
    if node_id in {"implement", "repair"}:
        payload["completion"] = normalize_completion(
            str(payload.get("completion", "")),
            prompt=instance["prompt"],
            entry_point=instance["entry_point"],
        )
    node_usage = _token_usage(usage, wall_ms=wall_ms, model=backend.model, reasoning_effort=backend.reasoning_effort)
    return payload, node_usage, raw


def _instance_hash(instance: dict[str, Any]) -> str:
    return hashlib.sha256(instance["prompt"].encode("utf-8")).hexdigest()[:16]


def generate_record(
    *,
    adapter: CodexCliAdapter,
    backend: BackendConfig,
    role: Role,
    instance: dict[str, Any],
    max_tokens: int,
    repair_retries: int = 1,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    node_usage: dict[str, Any] = {}
    raw_outputs: dict[str, str] = {}
    repair_attempts: list[dict[str, Any]] = []
    for node_id in MODEL_NODE_IDS:
        if node_id == "repair":
            public_result = run_public_examples(instance, state["implement"]["completion"])
            generated_result = run_generated_tests(
                instance,
                state["implement"]["completion"],
                list(state["generate_tests"].get("tests", [])),
            )
            state["candidate_public_feedback"] = public_result.payload
            state["candidate_generated_feedback"] = generated_result.payload
        payload, usage, raw = _call_node(
            adapter=adapter,
            backend=backend,
            node_id=node_id,
            instance=instance,
            state=state,
            max_tokens=max_tokens,
        )
        state[node_id] = payload
        node_usage[node_id] = usage
        raw_outputs[node_id] = raw
        if node_id == "repair":
            repair_attempts.append({"completion": payload["completion"], "raw": raw})
    candidate_passed_self_tests = bool(state.get("candidate_public_feedback", {}).get("passed")) and bool(
        state.get("candidate_generated_feedback", {}).get("passed")
    )
    repair_unchanged = state["implement"]["completion"] == state["repair"]["completion"]
    retry_index = 0
    while repair_unchanged and not candidate_passed_self_tests and retry_index < repair_retries:
        retry_index += 1
        state["repair_retry_feedback"] = {
            "reason": "previous_repair_returned_unchanged_failing_completion",
            "attempt": retry_index,
            "required_change": "Return a replacement body that addresses the failing public/generated feedback.",
        }
        payload, usage, raw = _call_node(
            adapter=adapter,
            backend=backend,
            node_id="repair",
            instance=instance,
            state=state,
            max_tokens=max_tokens,
        )
        state["repair"] = payload
        node_usage["repair"] = _merge_usage(node_usage["repair"], usage)
        raw_outputs["repair"] = raw
        repair_attempts.append({"completion": payload["completion"], "raw": raw, "retry": retry_index})
        repair_unchanged = state["implement"]["completion"] == state["repair"]["completion"]
    if repair_unchanged and not candidate_passed_self_tests:
        raise ValueError(
            f"Repair node returned an unchanged completion for failing candidate {instance['task_id']!r}"
        )
    return {
        "task_id": instance["task_id"],
        "role": role,
        "model": backend.model,
        "reasoning_effort": backend.reasoning_effort,
        "prompt_sha256_16": _instance_hash(instance),
        "spec_struct": state["understand_spec"],
        "plan_struct": state["plan"],
        "test_suite": state["generate_tests"],
        "completion": state["implement"]["completion"],
        "repaired_completion": state["repair"]["completion"],
        "selected_completion": state["repair"]["completion"],
        "completion_notes": state["implement"].get("notes", ""),
        "repair_summary": state["repair"].get("repair_summary", ""),
        "repair_status": (
            "unchanged_candidate_passed_self_tests"
            if repair_unchanged and candidate_passed_self_tests
            else "model_repair_output"
        ),
        "selection_reason": "repair_node_output",
        "node_usage": node_usage,
        "raw_outputs": raw_outputs,
        "repair_attempts": repair_attempts,
    }


def generate(
    *,
    role: Role,
    instances_path: Path,
    output_path: Path,
    config_path: str | None,
    limit: int | None,
    max_tokens: int,
    repair_retries: int,
) -> dict[str, Any]:
    ensure_step1_dirs()
    backend = _resolve_backend(role, config_path)
    rows = read_jsonl(instances_path, limit=limit)
    for row in rows:
        assert_public_solving_instance(row, context="generate_completions input")
    adapter = _adapter(backend)
    outputs: list[dict[str, Any]] = []
    for row in tqdm(rows, desc=f"generate_{role}", unit="task"):
        record = generate_record(
            adapter=adapter,
            backend=backend,
            role=role,
            instance=row,
            max_tokens=max_tokens,
            repair_retries=repair_retries,
        )
        outputs.append(record)
        print(
            json.dumps(
                {
                    "task_id": row["task_id"],
                    "role": role,
                    "model": backend.model,
                    "completion_chars": len(record["completion"]),
                    "repaired_completion_chars": len(record["repaired_completion"]),
                },
                sort_keys=True,
            )
        )
    write_jsonl(output_path, outputs)
    records = load_node_record_map(str(output_path))
    validate_node_record_coverage(
        instances=rows,
        records=records,
        record_jsonl=str(output_path),
        allow_mock=False,
    )
    return {
        "output": str(output_path),
        "instances": len(rows),
        "role": role,
        "model": backend.model,
        "reasoning_effort": backend.reasoning_effort,
        "transport": "codex_cli",
        "coverage": "full_164" if limit is None and len(rows) == 164 else "limited_smoke",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["seed", "cheap"], required=True)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--output", default=None)
    parser.add_argument("--config", default=None, help="Optional JSON/YAML Codex backend config.")
    parser.add_argument("--limit", type=int, default=None, help="Limit for real mini-smoke only.")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--repair-retries", type=int, default=1, help="Bounded retry when repair returns an unchanged failing completion.")
    args = parser.parse_args(argv)
    output = Path(args.output) if args.output else DEFAULT_OUTPUTS[args.role]
    manifest = generate(
        role=args.role,
        instances_path=Path(args.instances),
        output_path=output,
        config_path=args.config,
        limit=args.limit,
        max_tokens=args.max_tokens,
        repair_retries=args.repair_retries,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
