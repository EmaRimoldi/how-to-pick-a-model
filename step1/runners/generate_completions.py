"""Generate model-backed HumanEval completion JSONL files.

All model/API access for Step 1 lives here. The seed and online-loop runners
consume the resulting JSONL deterministically and never call a model.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from openai import OpenAI
from tqdm import tqdm

from runners.common import DATA_DIR, LOGS_DIR, ensure_step1_dirs, read_jsonl, write_jsonl
from runners.workflow import assert_public_solving_instance, load_completion_map, validate_completion_coverage


Role = Literal["seed", "cheap"]
DEFAULT_OUTPUTS = {
    "seed": LOGS_DIR / "seed_solver_completions.jsonl",
    "cheap": LOGS_DIR / "cheap_node_completions.jsonl",
}


@dataclass(frozen=True)
class BackendConfig:
    model: str
    api_key: str
    base_url: str
    api_mode: str
    timeout_seconds: float


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
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("API_KEY")
        or _config_value(config, "api_key")
        or _config_value(config, "openai", "api_key")
    )
    base_url = (
        os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
        or os.environ.get("API_BASE_URL")
        or _config_value(config, "base_url")
        or _config_value(config, "openai", "base_url")
    )
    api_mode = (
        os.environ.get("OPENAI_API_MODE")
        or _config_value(config, "api_mode")
        or _config_value(config, "openai", "api_mode")
        or "chat_completions"
    )
    timeout_seconds = float(
        os.environ.get("OPENAI_TIMEOUT_SECONDS")
        or _config_value(config, "timeout_seconds")
        or _config_value(config, "openai", "timeout_seconds")
        or 120
    )
    missing = []
    if not model:
        missing.append(model_env)
    if not api_key:
        missing.append("OPENAI_API_KEY")
    if not base_url:
        missing.append("OPENAI_BASE_URL")
    if missing:
        raise SystemExit(
            "Missing model backend configuration: "
            + ", ".join(missing)
            + ". Set environment variables or pass --config."
        )
    if api_mode not in {"chat_completions", "responses"}:
        raise SystemExit(f"Unsupported OPENAI_API_MODE/API mode {api_mode!r}; use chat_completions or responses")
    return BackendConfig(
        model=str(model),
        api_key=str(api_key),
        base_url=str(base_url),
        api_mode=str(api_mode),
        timeout_seconds=timeout_seconds,
    )


def _system_prompt(role: Role) -> str:
    tier = "strong seed solver" if role == "seed" else "cheap fast node agent"
    return (
        f"You are a {tier} for HumanEval. Return only the Python function body completion "
        "that should be appended directly after the provided prompt. Do not return markdown, "
        "imports, the function signature, explanations, tests, or any text outside the body. "
        "Do not use hidden tests, canonical solutions, or verifier code."
    )


def _user_prompt(instance: dict[str, Any]) -> str:
    return (
        "Complete this HumanEval function. The response must be only the indented function body.\n\n"
        f"task_id: {instance['task_id']}\n"
        f"entry_point: {instance['entry_point']}\n\n"
        "PROMPT:\n"
        f"{instance['prompt']}"
    )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip("\n")


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
            body = "\n".join(lines[start:end])
            return body
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


def _usage_payload(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return dict(usage)
    return {}


def _call_chat(client: OpenAI, backend: BackendConfig, messages: list[dict[str, str]], *, max_tokens: int, temperature: float) -> tuple[str, dict[str, Any]]:
    response = client.chat.completions.create(
        model=backend.model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content or ""
    return content, _usage_payload(response.usage)


def _call_responses(client: OpenAI, backend: BackendConfig, messages: list[dict[str, str]], *, max_tokens: int, temperature: float) -> tuple[str, dict[str, Any]]:
    response = client.responses.create(
        model=backend.model,
        input=messages,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )
    content = getattr(response, "output_text", "") or ""
    return content, _usage_payload(getattr(response, "usage", None))


def call_model(
    *,
    client: OpenAI,
    backend: BackendConfig,
    role: Role,
    instance: dict[str, Any],
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    messages = [
        {"role": "system", "content": _system_prompt(role)},
        {"role": "user", "content": _user_prompt(instance)},
    ]
    if backend.api_mode == "responses":
        return _call_responses(client, backend, messages, max_tokens=max_tokens, temperature=temperature)
    return _call_chat(client, backend, messages, max_tokens=max_tokens, temperature=temperature)


def _instance_hash(instance: dict[str, Any]) -> str:
    return hashlib.sha256(instance["prompt"].encode("utf-8")).hexdigest()[:16]


def generate(
    *,
    role: Role,
    instances_path: Path,
    output_path: Path,
    config_path: str | None,
    limit: int | None,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    ensure_step1_dirs()
    backend = _resolve_backend(role, config_path)
    rows = read_jsonl(instances_path, limit=limit)
    for row in rows:
        assert_public_solving_instance(row, context="generate_completions input")
    client = OpenAI(api_key=backend.api_key, base_url=backend.base_url, timeout=backend.timeout_seconds)
    outputs: list[dict[str, Any]] = []
    for row in tqdm(rows, desc=f"generate_{role}", unit="task"):
        started = time.perf_counter()
        raw, usage = call_model(
            client=client,
            backend=backend,
            role=role,
            instance=row,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        completion = normalize_completion(raw, prompt=row["prompt"], entry_point=row["entry_point"])
        outputs.append(
            {
                "task_id": row["task_id"],
                "completion": completion,
                "role": role,
                "model": backend.model,
                "api_mode": backend.api_mode,
                "prompt_sha256_16": _instance_hash(row),
                "wall_ms": int((time.perf_counter() - started) * 1000),
                "usage": usage,
                "raw_completion": raw,
            }
        )
        print(
            json.dumps(
                {
                    "task_id": row["task_id"],
                    "role": role,
                    "completion_chars": len(completion),
                    "model": backend.model,
                },
                sort_keys=True,
            )
        )
    write_jsonl(output_path, outputs)
    completions = load_completion_map(str(output_path))
    validate_completion_coverage(
        instances=rows,
        completions=completions,
        completion_jsonl=str(output_path),
        allow_mock=False,
    )
    manifest = {
        "output": str(output_path),
        "instances": len(rows),
        "role": role,
        "model": backend.model,
        "api_mode": backend.api_mode,
        "coverage": "limited_smoke" if limit is not None else "full_164",
    }
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["seed", "cheap"], required=True)
    parser.add_argument("--instances", default=str(DATA_DIR / "humaneval_public.jsonl"))
    parser.add_argument("--output", default=None)
    parser.add_argument("--config", default=None, help="Optional JSON/YAML backend config.")
    parser.add_argument("--limit", type=int, default=None, help="Limit for real mini-smoke only.")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args(argv)
    output = Path(args.output) if args.output else DEFAULT_OUTPUTS[args.role]
    manifest = generate(
        role=args.role,
        instances_path=Path(args.instances),
        output_path=output,
        config_path=args.config,
        limit=args.limit,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

