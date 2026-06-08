"""Codex CLI adapter for GPT/Codex model backends."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from vao.agents.anthropic_adapter import BackendUnavailable, ClaudeHaikuAdapter


class CodexCliAdapter(ClaudeHaikuAdapter):
    """Strict single-prompt adapter using the local `codex exec` transport.

    This keeps the C(a) batch protocol implemented by `ClaudeHaikuAdapter` and
    swaps only the completion transport. It is useful when Codex account auth is
    available locally but `OPENAI_API_KEY` is not exported for Responses API.
    """

    strict_failures = True

    def __init__(
        self,
        model_id: str,
        *,
        timeout_seconds: int = 900,
        max_tokens_distribution: int = 2048,
        max_tokens_edit: int = 4096,
        max_tokens_batch: int = 12000,
        retries: int = 1,
        edit_protocol: str = "structured_edits",
        reasoning_effort: str = "medium",
        sandbox: str = "read-only",
        use_output_schema: bool = False,
        extra_cli_args: list[str] | None = None,
        working_dir: str | Path | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            model_id=model_id,
            transport="codex_cli",
            temperature=float(kwargs.pop("temperature", 0.2)),
            timeout_seconds=timeout_seconds,
            max_tokens_distribution=max_tokens_distribution,
            max_tokens_edit=max_tokens_edit,
            max_budget_usd=None,
            retries=retries,
            edit_protocol=edit_protocol,
            max_tokens_batch=max_tokens_batch,
            **kwargs,
        )
        use_json_schema = bool(kwargs.pop("use_json_schema", False))
        self.reasoning_effort = str(reasoning_effort)
        self.sandbox = str(sandbox)
        self.use_output_schema = bool(use_output_schema or use_json_schema)
        self.extra_cli_args = list(extra_cli_args or [])
        self.working_dir = Path(working_dir).resolve() if working_dir else None

    def _complete(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        if shutil.which("codex") is None:
            raise BackendUnavailable("codex CLI not found")

        with tempfile.TemporaryDirectory(prefix="vao_codex_cli_") as tmp:
            tmp_dir = Path(tmp)
            output_path = tmp_dir / "last_message.json"
            cmd = [
                "codex",
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "-m",
                self.model_id,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "-s",
                self.sandbox,
                *(["-C", str(self.working_dir)] if self.working_dir else []),
                "--output-last-message",
                str(output_path),
            ]
            if self.use_output_schema:
                schema_path = tmp_dir / "schema.json"
                schema_path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
                cmd += ["--output-schema", str(schema_path)]
            prompt_with_schema = prompt
            if not self.use_output_schema:
                prompt_with_schema = prompt + "\n\nRequired JSON schema:\n" + json.dumps(schema, sort_keys=True)
            cmd += [*self.extra_cli_args, prompt_with_schema]
            started = time.perf_counter()
            proc = subprocess.run(
                cmd,
                text=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=self.timeout_seconds,
                cwd=str(self.working_dir) if self.working_dir else None,
            )
            elapsed = time.perf_counter() - started
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout)[-2000:]
                raise RuntimeError(f"codex_cli_failed:{proc.returncode}:{detail}")
            if output_path.exists():
                raw = output_path.read_text(encoding="utf-8")
            else:
                raw = _last_jsonish_stdout_block(proc.stdout)
            if not raw.strip():
                raise RuntimeError("codex_cli_empty_output")
            return raw, {
                "transport": "codex_cli",
                "usage": _parse_codex_stdout_usage(proc.stdout + "\n" + proc.stderr),
                "cost_usd": None,
                "elapsed_wall_seconds": elapsed,
                "model": self.model_id,
                "reasoning_effort": self.reasoning_effort,
                "max_tokens_requested": int(max_tokens),
                "raw_cli_result": {
                    "stdout_tail": proc.stdout[-1000:],
                    "stderr_tail": proc.stderr[-1000:],
                },
            }

    def _complete_persistent(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        return self._run_codex_persistent(["exec"], prompt, schema, max_tokens)

    def _resume_persistent(self, session_id: str, prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        return self._run_codex_persistent(["exec", "resume", session_id], prompt, schema, max_tokens)

    def _run_codex_persistent(self, base_cmd: list[str], prompt: str, schema: dict[str, Any], max_tokens: int) -> tuple[str, dict[str, Any]]:
        if shutil.which("codex") is None:
            raise BackendUnavailable("codex CLI not found")
        with tempfile.TemporaryDirectory(prefix="vao_codex_cli_session_") as tmp:
            tmp_dir = Path(tmp)
            output_path = tmp_dir / "last_message.json"
            schema_path = tmp_dir / "schema.json"
            schema_path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
            prompt_input = prompt
            if base_cmd[:2] == ["exec", "resume"]:
                command_prefix = ["codex", "exec", "resume"]
                command_suffix = [base_cmd[2], "-"]
                schema_args: list[str] = []
                sandbox_args: list[str] = []
                prompt_input = prompt + "\n\nReturn only valid JSON matching this schema:\n" + json.dumps(schema, sort_keys=True)
            else:
                command_prefix = ["codex", "exec"]
                command_suffix = ["-"]
                schema_args = ["--output-schema", str(schema_path)]
                sandbox_args = ["-s", self.sandbox]
            cmd = [
                *command_prefix,
                "--skip-git-repo-check",
                "-m",
                self.model_id,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                *sandbox_args,
                *(["-C", str(self.working_dir)] if self.working_dir else []),
                "--json",
                "--output-last-message",
                str(output_path),
                *schema_args,
                *self.extra_cli_args,
                *command_suffix,
            ]
            started = time.perf_counter()
            proc = subprocess.run(
                cmd,
                text=True,
                input=prompt_input,
                capture_output=True,
                timeout=self.timeout_seconds,
                cwd=str(self.working_dir) if self.working_dir else None,
            )
            elapsed = time.perf_counter() - started
            if proc.returncode != 0:
                detail = f"STDERR:\n{proc.stderr[-4000:]}\nSTDOUT:\n{proc.stdout[-4000:]}"
                raise RuntimeError(f"codex_cli_persistent_failed:{proc.returncode}:{detail}")
            raw = output_path.read_text(encoding="utf-8") if output_path.exists() else _last_jsonish_stdout_block(proc.stdout)
            if not raw.strip():
                raise RuntimeError("codex_cli_persistent_empty_output")
            session_id = _parse_codex_session_id(proc.stdout)
            return raw, {
                "transport": "codex_cli_persistent",
                "usage": _parse_codex_stdout_usage(proc.stdout + "\n" + proc.stderr),
                "cost_usd": None,
                "elapsed_wall_seconds": elapsed,
                "model": self.model_id,
                "reasoning_effort": self.reasoning_effort,
                "max_tokens_requested": int(max_tokens),
                "session_id": session_id,
                "raw_cli_result": {
                    "stdout_tail": proc.stdout[-1000:],
                    "stderr_tail": proc.stderr[-1000:],
                },
            }


def _last_jsonish_stdout_block(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            return line
    return ""


def _parse_codex_stdout_usage(stdout: str) -> dict[str, Any]:
    json_usage: dict[str, int] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if not isinstance(usage, dict):
            continue
        for key, value in usage.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                json_usage[key] = json_usage.get(key, 0) + value
            elif isinstance(value, float):
                json_usage[key] = json_usage.get(key, 0) + int(value)
    if json_usage:
        if "total_tokens" not in json_usage:
            json_usage["total_tokens"] = int(json_usage.get("input_tokens", 0)) + int(json_usage.get("output_tokens", 0))
        return json_usage

    lines = [line.strip() for line in stdout.splitlines()]
    for index, line in enumerate(lines):
        if line == "tokens used" and index + 1 < len(lines):
            try:
                return {"total_tokens": int(float(lines[index + 1].replace(",", "")))}
            except ValueError:
                return {"tokens_used_raw": lines[index + 1]}
    return {}


def _parse_codex_session_id(stdout: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _find_session_id(payload)
        if found:
            return found
    return None


def _find_session_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("session_id", "conversation_id", "thread_id"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return item
        for item in value.values():
            found = _find_session_id(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_session_id(item)
            if found:
                return found
    return None
